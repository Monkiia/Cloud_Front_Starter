import json
import boto3

def lambda_handler(event, context):
    # TODO implement
    message = event["messages"][0]["unstructured"]["text"]
    msgs = [{
        "type": 'unstructured',
        "unstructured": {
          "text": "Welcome to Lambda This is to repeat" + message
      }
    }]
    client = boto3.client('lex-runtime')
    client_response = client.post_text(
        botName='OrderFlowersV',
        botAlias='OrderFlowersV',
        userId='lf0',
        inputText=message)
    msgs = [{
        "type": 'unstructured',
        "unstructured": {
          "text": client_response['message']
      }
    }]
    response = {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Headers" : "Content-Type",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
        },
        "messages": msgs
    }
    return response
