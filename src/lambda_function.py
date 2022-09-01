# Copyright 2010-2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Altered from original by Adam Winter
#
# This file is licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License. A copy of the
# License is located at
#
# http://aws.amazon.com/apache2.0/
#
# This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS
# OF ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import os
import boto3
import email
import re
import html
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
import json
from datetime import datetime
region = os.environ['Region']

FORWARD_ADDRESSES = "bhimaniheet@gmail.com"
FROM_ADDRESS = "support@xploitwizer.com"
EMAIL_DOMAIN = "xploitwizer.com"  # my aws receiver email domain
SPAMMER_DOMAINS = map(re.compile, ["example.com"])
SPAMMER_EMAILS = map(re.compile, ["spammer-jack@example.com"])

def print_with_timestamp(*args):
	print(datetime.utcnow().isoformat(), *args)

def get_message_from_s3(action,message_id):

    incoming_email_bucket = action['bucketName']
    incoming_email_prefix = action['objectKey']

    object_path = incoming_email_prefix
    # if incoming_email_prefix:
    #     object_path = (incoming_email_prefix + "/" + message_id)
    # else:
    #     object_path = message_id

    object_http_path = (f"http://s3.console.aws.amazon.com/s3/object/{incoming_email_bucket}/{object_path}?region={region}")

    # Create a new S3 client.
    client_s3 = boto3.client("s3")

    # Get the email object from the S3 bucket.
    object_s3 = client_s3.get_object(Bucket=incoming_email_bucket,
        Key=object_path)
    # Read the content of the message.
    file = object_s3['Body'].read()

    file_dict = {
        "file": file,
        "path": object_http_path
    }

    return file_dict

def create_message(file_dict):

    stringMsg = file_dict['file'].decode('utf-8')

    # Create a MIME container.
    msg = MIMEMultipart('alternative')

    sender = FROM_ADDRESS
    recipient = FORWARD_ADDRESSES

    # Parse the email body.
    mailobject = email.message_from_string(file_dict['file'].decode('utf-8'))
    #print(mailobject.as_string())

    # Get original sender for reply-to
    from_original = mailobject['Return-Path']
    from_original = from_original.replace('<', '');
    from_original = from_original.replace('>', '');
    print(from_original)

    # Create a new subject line.
    subject = mailobject['Subject']
    print(subject)

    if mailobject.is_multipart():

        #The quick and dirty way.  If you don't like this, use the for loop below it.
        index = stringMsg.find('Content-Type: multipart/')
        stringBody = stringMsg[index:]
        #print(stringBody)
        stringData = 'Subject: ' + subject + '\nTo: ' + sender + '\nreply-to: ' + from_original + '\n' + stringBody

        message = {
            "Source": sender,
            "Destinations": recipient,
            "Data": stringData
        }
        return message

        for part in mailobject.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))

            # case for each common content type
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                bodyPart = MIMEText(part.get_payload(decode=True), 'plain', part.get_content_charset())
                msg.attach(bodyPart)

            if ctype == 'text/html' and 'attachment' not in cdispo:
                mt = MIMEText(part.get_payload(decode=True), 'html', part.get_content_charset())
                email.encoders.encode_quopri(mt)
                del mt['Content-Transfer-Encoding']
                mt.add_header('Content-Transfer-Encoding', 'quoted-printable')
                msg.attach(mt)

            if 'attachment' in cdispo and 'image' in ctype:
                mi = MIMEImage(part.get_payload(decode=True), ctype.replace('image/', ''))
                del mi['Content-Type']
                del mi['Content-Disposition']
                mi.add_header('Content-Type', ctype)
                mi.add_header('Content-Disposition', cdispo)
                msg.attach(mi)

            if 'attachment' in cdispo and 'application' in ctype:
                ma = MIMEApplication(part.get_payload(decode=True), ctype.replace('application/', ''))
                del ma['Content-Type']
                del ma['Content-Disposition']
                ma.add_header('Content-Type', ctype)
                ma.add_header('Content-Disposition', cdispo)
                msg.attach(ma)


    # not multipart - i.e. plain text, no attachments, keeping fingers crossed
    else:
        body = MIMEText(mailobject.get_payload(decode=True), 'UTF-8')
        msg.attach(body)

    # The file name to use for the attached message. Uses regex to remove all
    # non-alphanumeric characters, and appends a file extension.
    filename = re.sub('[^0-9a-zA-Z]+', '_', subject_original)

    # Add subject, from and to lines.
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg['reply-to'] = mailobject['Return-Path']

    # Create a new MIME object.
    att = MIMEApplication(file_dict["file"], filename)
    att.add_header("Content-Disposition", 'attachment', filename=filename)

    # Attach the file object to the message.
    msg.attach(att)
    message = {
        "Source": sender,
        "Destinations": recipient,
        "Data": msg.as_string()
    }
    return message

def send_email(message):
    aws_region = os.environ['Region']
# Create a new SES client.
    client_ses = boto3.client('ses', region)
    # Send the email.
    try:
        #Provide the contents of the email.
        response = client_ses.send_raw_email(
            Source=message['Source'],
            Destinations=[
                message['Destinations'],"bhimaniheet23@gmail.com"
            ],
            RawMessage={
                'Data':message['Data']
            }
        )

    # Display an error if something goes wrong.
    except ClientError as e:
        print('send email ClientError Exception')
        output = e.response['Error']['Message']
    else:
        output = "Email sent! Message ID: " + response['MessageId']

    return output

def lambda_handler(event, context):
    # Get the unique ID of the message. This corresponds to the name of the file
    # in S3.
    ses_notification = event['Records'][0]['Sns']
    message = json.loads(ses_notification["Message"])
    message_id = message['mail']['messageId']
    # message_id = event['Records'][0]['ses']['mail']['messageId']
    print(f"Received message ID {message_id}")

    receipt = message['receipt']
    print_with_timestamp(receipt['recipients'])
    # Check if any spam check failed
    if (receipt['spfVerdict']['status'] == 'FAIL' or
                        receipt['dkimVerdict']['status'] == 'FAIL' or
                        receipt['spamVerdict']['status'] == 'FAIL' or
                        receipt['virusVerdict']['status'] == 'FAIL'):

                send_bounce_params = {
                    'OriginalMessageId': message_id,
                    'BounceSender': 'mailer-daemon@{}'.format(EMAIL_DOMAIN),
                    'MessageDsn': {
                        'ReportingMta': 'dns; {}'.format(EMAIL_DOMAIN),
                        'ArrivalDate': datetime.now().isoformat()
                    },
                    'BouncedRecipientInfoList': []
                }

                for recipient in receipt['recipients']:
                    send_bounce_params['BouncedRecipientInfoList'].append({
                        'Recipient': recipient,
                        'BounceType': 'ContentRejected'
                    })

                print_with_timestamp('Bouncing message with parameters:')
                print_with_timestamp(json.dumps(send_bounce_params))

                try:
                    ses_client = boto3.client('ses')
                    bounceResponse = ses_client.send_bounce(**send_bounce_params)
                    print_with_timestamp('Bounce for message ', message_id, ' sent, bounce message ID: ', bounceResponse['MessageId'])
                    return {'disposition': 'stop_rule_set'}
                except Exception as e:
                    print_with_timestamp(e)
                    print_with_timestamp('An error occurred while sending bounce for message: ', message_id)
                    raise e
    
    else:
        print_with_timestamp('Accepting message:', message_id)
    
    # now distribute to list:
    action = receipt['action']
    if (action['type'] != "S3"):
        print("Mail body is not saved to S3. Or I have done sth wrong.")
        return None

    # Retrieve the file from the S3 bucket.
    file_dict = get_message_from_s3(action,message_id)

    # Create the message.
    message = create_message(file_dict)

    # Send the email and print the result.
    result = send_email(message)
    print(result)