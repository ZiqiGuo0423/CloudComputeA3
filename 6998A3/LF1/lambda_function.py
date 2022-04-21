import boto3
import json
import email
import os

#from sagemaker.mxnet.model import MXNetPredictor
from sms_spam_classifier_utilities import one_hot_encode
from sms_spam_classifier_utilities import vectorize_sequences

runtime= boto3.client('runtime.sagemaker')
vocabulary_length = 9013

def send_email(To_address,date,subject,From_address,body,classification,CLASSIFICATION_CONFIDENCE_SCORE):
    print('ready to enter SES')
    
    SENDER = "Spam/Ham Detection <hz2759@columbia.edu>"

    RECIPIENT = To_address

    AWS_REGION = "us-east-1"

    SUBJECT = "Email Classfication"

    # The email body for recipients with non-HTML email clients.
    BODY_TEXT = 'We received your email sent at: ' + date + ' with the subject: ' + subject + ' to: ' + From_address + '\n\nHere is the email body:\n' + body +'\nThe email was categorized as ' + classification + ' with a ' + CLASSIFICATION_CONFIDENCE_SCORE + '% confidence.'
    print(BODY_TEXT)
    
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
            Source=SENDER,

        )
    # Display an error if something goes wrong.
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent!\n Message ID:"),
        print(response['MessageId'])
    return(response['MessageId'])
 
def lambda_handler(event, context):

    print("Endpoint environment variable: " + os.environ['id'])
    ENDPOINT_NAME =  os.environ['id']
    print(ENDPOINT_NAME)

    data = json.loads(json.dumps(event))
    print('data:',data)
    
    # retrieve the eamil from s3
    s3 = boto3.client("s3")
    file_obj = data["Records"][0]
    filename = str(file_obj["s3"]['object']['key'])
    print("filename: ", filename)
    fileObj = s3.get_object(Bucket = "email-bucket-cloudformation", Key=filename)
    print("email has been gotten!")
    
    msg = email.message_from_bytes(fileObj['Body'].read())
    print('msg:',msg)
    
    # retrieve the toAdd and fromAdd from email
    toAddress = msg.get('To')
    print('ToAdd:',toAddress)
    fromAddress = msg.get('From').split(",")
    start = fromAddress[0].find('<')
    end = fromAddress[0].find('>')
    faddr = fromAddress[0][start+1:end]
    print('FromAdd:',faddr)
    
    #retrieve the sent date
    Date = msg.get('Date')
    print('date:',Date)
    
    #retrieve the subject
    Subject = msg.get('Subject')
    
    
    # retrieve the body of the email
    if msg.is_multipart():
        for part in msg.get_payload():
            if part.get_content_type() == 'text/plain':
                body = part.get_payload()
                print('body:',body)
                
    else:
        body = msg.get_payload()
        print('body1:',body)
    
    
    
    payload = []
    payload.append(body.strip())
    print('payload:',payload)
    
    #payload = ["FreeMsg: Txt: CALL to No: 86888 & claim your reward of 3 hours talk time to use from your phone now! ubscribe6GBP/ mnth inc 3hrs 16 stop?txtStop"] 
    
    one_hot_test_messages = one_hot_encode(payload, vocabulary_length)
    encoded_test_messages = vectorize_sequences(one_hot_test_messages, vocabulary_length)
    print('hot:',one_hot_test_messages)
    print('encode:',encoded_test_messages)
    
    
    print('list:',encoded_test_messages.tolist())
    response = runtime.invoke_endpoint(EndpointName=ENDPOINT_NAME,
                                       ContentType='application/json',
                                       Body=json.dumps(encoded_test_messages.tolist()))
    print(response)

    result = json.loads(response['Body'].read().decode('utf-8'))
    
    try:
        print('Result :', result)
    except Exception as e:
        print(e)
    
    if result['predicted_label'][0][0] == 1.0:
        classification = 'SPAM'
        CLASSIFICATION_CONFIDENCE_SCORE = float(result['predicted_probability'][0][0]) * 100
        
    else:
        classification = 'HAM'
        CLASSIFICATION_CONFIDENCE_SCORE = 100 - float(result['predicted_probability'][0][0]) * 100
    
    print('classification:', classification)
    print('score:', CLASSIFICATION_CONFIDENCE_SCORE)    
    
    #send email back
    resp = send_email(faddr,Date,Subject,toAddress,body,classification,str(CLASSIFICATION_CONFIDENCE_SCORE))
    
    responses = {
                    'statusCode': 200,
                    'body': 'Email Sent:'+resp
                }
    return responses
    