from fastapi import FastAPI, HTTPException, Depends
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient, PartitionKey
from datetime import datetime
from typing import List, Optional

app = FastAPI()

class CosmosConversationClient():
    def __init__(self, cosmosdb_endpoint: str, credential: any, database_name: str, container_name: str):
        self.cosmosdb_endpoint = cosmosdb_endpoint
        self.credential = credential
        self.database_name = database_name
        self.container_name = container_name
        self.cosmosdb_client = CosmosClient(self.cosmosdb_endpoint, credential=credential)
        self.database_client = self.cosmosdb_client.get_database_client(database_name)
        self.container_client = self.database_client.get_container_client(container_name)

    def ensure(self):
        try:
            if not self.cosmosdb_client or not self.database_client or not self.container_client:
                return False
            
            container_info = self.container_client.read()
            if not container_info:
                return False
            
            return True
        except:
            return False

    def create_conversation(self, user_id, title = ''):
        conversation = {
            'id': str(uuid.uuid4()),  
            'type': 'conversation',
            'createdAt': datetime.utcnow().isoformat(),  
            'updatedAt': datetime.utcnow().isoformat(),  
            'userId': user_id,
            'title': title
        }
        resp = self.container_client.upsert_item(conversation)  
        if resp:
            return resp
        else:
            return False
    
    def upsert_conversation(self, conversation):
        resp = self.container_client.upsert_item(conversation)
        if resp:
            return resp
        else:
            return False

    def delete_conversation(self, user_id, conversation_id):
        conversation = self.container_client.read_item(item=conversation_id, partition_key=user_id)        
        if conversation:
            resp = self.container_client.delete_item(item=conversation_id, partition_key=user_id)
            return resp
        else:
            return True

    def delete_messages(self, conversation_id, user_id):
        messages = self.get_messages(user_id, conversation_id)
        response_list = []
        if messages:
            for message in messages:
                resp = self.container_client.delete_item(item=message['id'], partition_key=user_id)
                response_list.append(resp)
            return response_list

    def get_conversations(self, user_id, sort_order = 'DESC'):
        parameters = [
            {'name': '@userId', 'value': user_id}
        ]
        query = f"SELECT * FROM c where c.userId = @userId and c.type='conversation' order by c.updatedAt {sort_order}"
        conversations = list(self.container_client.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        if len(conversations) == 0:
            return []
        else:
            return conversations

    def get_conversation(self, user_id, conversation_id):
        parameters = [
            {'name': '@conversationId', 'value': conversation_id},
            {'name': '@userId', 'value': user_id}
        ]
        query = f"SELECT * FROM c where c.id = @conversationId and c.type='conversation' and c.userId = @userId"
        conversation = list(self.container_client.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        if len(conversation) == 0:
            return None
        else:
            return conversation[0]
 
    def create_message(self, conversation_id, user_id, input_message: dict):
        message = {
            'id': str(uuid.uuid4()),
            'type': 'message',
            'userId' : user_id,
            'createdAt': datetime.utcnow().isoformat(),
            'updatedAt': datetime.utcnow().isoformat(),
            'conversationId' : conversation_id,
            'role': input_message['role'],
            'content': input_message['content']
        }
        resp = self.container_client.upsert_item(message)  
        if resp:
            conversation = self.get_conversation(user_id, conversation_id)
            conversation['updatedAt'] = message['createdAt']
            self.upsert_conversation(conversation)
            return resp
        else:
            return False

    def get_messages(self, user_id, conversation_id):
        parameters = [
            {'name': '@conversationId', 'value': conversation_id},
            {'name': '@userId', 'value': user_id}
        ]
        query = f"SELECT * FROM c WHERE c.conversationId = @conversationId AND c.type='message' AND c.userId = @userId ORDER BY c.timestamp ASC"
        messages = list(self.container_client.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
        if len(messages) == 0:
            return []
        else:
            return messages


# Dependency to get the CosmosConversationClient instance
def get_cosmos_client():
    return CosmosConversationClient(
        cosmosdb_endpoint="your_cosmosdb_endpoint",
        credential=DefaultAzureCredential(),
        database_name="your_database_name",
        container_name="your_container_name",
    )

@app.get("/conversations/{user_id}", response_model=List[dict])
async def get_conversations(
    user_id: str,
    sort_order: str = 'DESC',
    cosmos_client: CosmosConversationClient = Depends(get_cosmos_client),
):
    try:
        conversations = cosmos_client.get_conversations(user_id, sort_order)
        return conversations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/conversations/{user_id}", response_model=dict)
async def create_conversation(
    user_id: str,
    title: Optional[str] = '',
    cosmos_client: CosmosConversationClient = Depends(get_cosmos_client),
):
    try:
        conversation = cosmos_client.create_conversation(user_id, title)
        return conversation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
