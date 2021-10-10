import json
import boto3
import logging
from boto3.dynamodb.conditions import Key,Attr
from botocore.vendored import requests
from requests.auth import HTTPBasicAuth
from botocore.exceptions import ClientError
import random

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def helper(text):
    Perfect = ['Chinese','Japanese','Italian','Thai','Mexican']
    if text in Perfect:
        return text
    if text.lower() == 'chinese':
        return 'Chinese'
    if text.lower() == 'japanese':
        return 'Japanese'
    if text.lower() == 'italian' :
        return 'Italian'
    if text.lower() == 'thai':
        return "Thai"
    if text.lower() == 'mexican':
        return "Mexican"

def pullSQS():
    SQS = boto3.client("sqs")
    s = SQS.get_queue_url(QueueName = "DineQueue")["QueueUrl"]
    response = SQS.receive_message(
        QueueUrl = s,
        MessageAttributeNames = ['All'])
    try:
        message = response["Messages"][0]
    except:
        logger.debug("No Messages or Error")
        return None
    logger.debug(message)
    messages = response["Messages"]
    for msg in messages:
        SQS.delete_message(
            QueueUrl = s,
            ReceiptHandle = msg['ReceiptHandle'])
    return messages

def backup_incase_es_down(cuisine_msg):
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('yelp_restaurant')
    count = 0
    result = ""

    scan_kwags = {
        'FilterExpression' : Key('cuisine').eq(helper(cuisine_msg))
    }
    search_cuisine = table.scan(**scan_kwags)
    while count < 3:
        search_item = search_cuisine['Items'][count]
        search_name = search_item['name']
        search_address = search_item['address']
        result = result + str(count) + search_name + search_address + ". "
        count = count + 1
    return result

def es_start(cuisine_msg):
    query = "https://search-assignment1-y7e244cuvw5v26h5ot4ogbxjty.us-east-1.es.amazonaws.com/restaurants/_search?q={}&pretty=true".format(helper(cuisine_msg))
    result = requests.get(query,auth=HTTPBasicAuth('fall2021','CloudComputing2021!'))
    listofrestaurants = (json.loads(result.content.decode('utf-8')))["hits"]["hits"]
    listlen = len(listofrestaurants)
    listofids = []
    for i in range(5):
        searchindex = random.randint(0,listlen-1)
        rest = (listofrestaurants[searchindex])['_source']['id']
        listofids.append(rest)
    logger.debug(listofids)
    return listofids
    
def fetch_db(listofids):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('yelp-restaurants')
    count = 0
    result = ""
    for id in listofids:
        scan_kwags = {
            'FilterExpression' : Key('id').eq(id)
        }
        search_cuisine = table.scan(**scan_kwags)
        search_item = search_cuisine['Items'][0]
        search_name = search_item['name']
        search_address = search_item['address']
        count = count + 1
        result = result + str(count) + ". " + search_name + " located at " + search_address + ". "
        if count == 3:
            break
    return result

def lambda_handler(event, context):
    # TODO implement
    responses = pullSQS()
    if responses is None:
        return ""
    logger.debug("reponses length {}".format(len(responses)))
    countsent=0
    for response in responses:
        location = response["MessageAttributes"]["Location"]["StringValue"]
        cuisine = response["MessageAttributes"]["Cuisine"]["StringValue"]
        date = response["MessageAttributes"]["Date"]["StringValue"]
        time = response["MessageAttributes"]["Time"]["StringValue"]
        numberofpeople = response["MessageAttributes"]["NumberofPeople"]["StringValue"]
        emailaddress = response["MessageAttributes"]["EmailAddress"]["StringValue"]
        #result = backup_incase_es_down(cuisine)
        listofids = es_start(cuisine)
        result = fetch_db(listofids)
        responsestart = "Hello! Here are my {} restaurant suggestion".format(cuisine) + " for {} people".format(numberofpeople) + " for {} ".format(date) + " at time {} ".format(time)
        finalresult = responsestart + result
        RECIPIENT = emailaddress
        SENDER = "shenshengchengrad@gmail.com"
        AWS_REGION = "us-east-1"
        
        # The subject line for the email.
        SUBJECT = "Amazon SES Test (SDK for Python)"
        
        # The email body for recipients with non-HTML email clients.
        BODY_TEXT = (finalresult)
                    
        # The HTML body of the email.
        BODY_HTML = finalresult           
        
        # The character encoding for the email.
        CHARSET = "UTF-8"
        
        # Create a new SES resource and specify a region.
        client = boto3.client('ses',region_name=AWS_REGION)
        
        # Try to send the email.
        try:
            #Provide the contents of the email.
            response = client.send_email(
                Destination={
                    'ToAddresses': [
                        RECIPIENT,
                    ],
                },
                Message={
                    'Body': {
                        'Html': {
                            'Charset': CHARSET,
                            'Data': BODY_HTML,
                        },
                        'Text': {
                            'Charset': CHARSET,
                            'Data': BODY_TEXT,
                        },
                    },
                    'Subject': {
                        'Charset': CHARSET,
                        'Data': SUBJECT,
                    },
                },
                Source=SENDER
            )
        # Display an error if something goes wrong.	
        except ClientError as e:
            print(e.response['Error']['Message'])
        else:
            logger.debug("Email sent! Message ID:"),
            logger.debug(response['MessageId'])
            countsent = countsent + 1
    return countsent