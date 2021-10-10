"""
This sample demonstrates an implementation of the Lex Code Hook Interface
in order to serve a sample bot which manages orders for flowers.
Bot, Intent, and Slot models which are compatible with this sample can be found in the Lex Console
as part of the 'OrderFlowers' template.

For instructions on how to set up and test this bot, as well as additional samples,
visit the Lex Getting Started documentation http://docs.aws.amazon.com/lex/latest/dg/getting-started.html.
"""
import math
import dateutil.parser
import datetime
import time
import os
import logging
import re
import boto3
import json

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


""" --- Helpers to build responses which match the structure of the necessary dialog actions --- """


def get_slots(intent_request):
    return intent_request['currentIntent']['slots']


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }


""" --- Helper Functions --- """
regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
 
# Define a function for
# for validating an Email
 
 
def check(email):
 
    # pass the regular expression
    # and the string into the fullmatch() method
    if(re.fullmatch(regex, email)):
        return True
 
    else:
        return False

def parse_int(n):
    try:
        return int(n)
    except ValueError:
        return float('nan')


def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is None:
        return {
            "isValid": is_valid,
            "violatedSlot": violated_slot,
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def isvalid_date(date):
    try:
        dateutil.parser.parse(date)
        return True
    except ValueError:
        return False


def validate_order_flowers(location,flower_type, date, pickup_time,email_address,people_num):
    flower_types = ['chinese', 'italian', 'mexican','thai','japanese']
    if location is not None and location.lower() != 'manhatten':
        return build_validation_result(False,
                                       'Location',
                                       'We do not have {}, Currently we only support Manhatten, please enter Manhatten!'.format(location))
    if flower_type is not None and flower_type.lower() not in flower_types:
        return build_validation_result(False,
                                       'Cuisine',
                                       'We do not have {}, would you like a different type of cuisine?  '
                                       'Our most popular cuisine is Thai'.format(flower_type))
    if people_num is not None:
        if parse_int(people_num) <= 0 or parse_int(people_num) > 20:
            return build_validation_result(False, 'PeopleNumber', 'People to host should be >= 1 and <= 20')
    if date is not None:
        if not isvalid_date(date):
            return build_validation_result(False, 'PickupDate', 'I did not understand that, what date would you like to eat the cuisine up?')
        elif datetime.datetime.strptime(date, '%Y-%m-%d').date() < datetime.date.today():
            return build_validation_result(False, 'PickupDate', 'You can eat the cuisine from today onwards.  What day would you like to eat them up?')

    if pickup_time is not None:
        if len(pickup_time) != 5:
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'PickupTime', None)

        hour, minute = pickup_time.split(':')
        hour = parse_int(hour)
        minute = parse_int(minute)
        if math.isnan(hour) or math.isnan(minute):
            # Not a valid time; use a prompt defined on the build-time model.
            return build_validation_result(False, 'PickupTime', None)

        if hour < 10 or hour > 16:
            # Outside of business hours
            return build_validation_result(False, 'PickupTime', 'Our business hours are from ten a m. to five p m. Can you specify a time during this range?')
        timenow = datetime.datetime.now()
        if datetime.datetime.strptime(date, '%Y-%m-%d').date() == datetime.date.today() and hour < timenow.hour:
            return build_validation_result(False, 'PickupTime', 'Must have been larger than our current time')
        
        if datetime.datetime.strptime(date, '%Y-%m-%d').date() == datetime.date.today() and hour == timenow.hour and minute <= timenow.minute:
            return build_validation_result(False, 'PickupTime', 'Must have been larger than our current time')
        
    if email_address is not None:
        is_valid_email = check(email_address)
        if (not is_valid_email):
            return build_validation_result(False, 'EmailAddress', "Your email address is not correct")
    return build_validation_result(True, None, None)


""" --- Functions that control the bot's behavior --- """
def greeting(intent_request):
      return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': 'Hi there, how can I help?'})
                  
def thankyou(intent_request):
      return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': 'You are welcome'})                  

def order_flowers(intent_request):
    """
    Performs dialog management and fulfillment for ordering flowers.
    Beyond fulfillment, the implementation of this intent demonstrates the use of the elicitSlot dialog action
    in slot validation and re-prompting.
    """
    logger.debug(get_slots(intent_request))
    location = get_slots(intent_request)["Location"]
    flower_type = get_slots(intent_request)["Cuisine"]
    people_num = get_slots(intent_request)["PeopleNumber"]
    date = get_slots(intent_request)["PickupDate"]
    pickup_time = get_slots(intent_request)["PickupTime"]
    email_address = get_slots(intent_request)["EmailAddress"]
    source = intent_request['invocationSource']

    if source == 'DialogCodeHook':
        # Perform basic validation on the supplied input slots.
        # Use the elicitSlot dialog action to re-prompt for the first violation detected.
        slots = get_slots(intent_request)

        validation_result = validate_order_flowers(location,flower_type, date, pickup_time,email_address,people_num)
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(intent_request['sessionAttributes'],
                               intent_request['currentIntent']['name'],
                               slots,
                               validation_result['violatedSlot'],
                               validation_result['message'])

        # Pass the price of the flowers back through session attributes to be used in various prompts defined
        # on the bot model.
        output_session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
        if flower_type is not None:
            output_session_attributes['Price'] = len(flower_type) * 5  # Elegant pricing model

        return delegate(output_session_attributes, get_slots(intent_request))

    # Order the flowers, and rely on the goodbye message of the bot to define the message to the end user.
    # In a real bot, this would likely involve a call to a backend service.
    logger.debug(get_slots(intent_request))
    slots = get_slots(intent_request)
    SQS = boto3.client("sqs")
    s = SQS.get_queue_url(QueueName = "DineQueue")["QueueUrl"]
    SQS.send_message(
        QueueUrl = s,
        MessageBody = "Message from LF1",
        MessageAttributes = {
            "Location" : {
                "StringValue" : str(slots["Location"]),
                "DataType" : "String"
            },
            "Cuisine" : {
                "StringValue" : str(slots["Cuisine"]),
                "DataType" : "String"
            },
            "NumberofPeople" : {
                "StringValue" : str(slots["PeopleNumber"]),
                "DataType" : "String"
            },
            "Date" : {
                "StringValue" : str(slots["PickupDate"]),
                "DataType" : "String"
            },
            "Time" : {
                "StringValue" : str(slots["PickupTime"]),
                "DataType" : "String"
            },
            "EmailAddress" : {
                "StringValue" : str(slots["EmailAddress"]),
                "DataType" : "String"
            }
        })
    return close(intent_request['sessionAttributes'],
                 'Fulfilled',
                 {'contentType': 'PlainText',
                  'content': 'Thanks, your order for {} has been placed and will be ready for pickup by {} on {}'.format(flower_type, pickup_time, date)})


""" --- Intents --- """


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'OrderFlowers':
        return order_flowers(intent_request)
    if intent_name == 'Greeting':
        return greeting(intent_request)
    if intent_name == 'ThankYou':
        return thankyou(intent_request)
    raise Exception('Intent with name ' + intent_name + ' not supported')


""" --- Main handler --- """


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))

    return dispatch(event)
