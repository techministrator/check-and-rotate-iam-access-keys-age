import datetime
import os
import boto3
from botocore.exceptions import ClientError

TODAY = datetime.datetime.now().date() 
MAX_KEYS_PER_USER = 2

SES_EMAIL = os.environ['SES_EMAIL']
SES_REGION = os.environ['SES_REGION']
IAM_EMAIL_TAG_KEY = os.environ['IAM_EMAIL_TAG_KEY']
S3_CSV_BUCKET = os.environ['S3_CSV_BUCKET']
LAST_CHECK_DATE_TAG_KEY = os.environ['LAST_CHECK_DATE_TAG_KEY']
LAST_CHECK_OLD_KEY_TAG_KEY = os.environ['LAST_CHECK_OLD_KEY_TAG_KEY']
WARNING_DAYS = int(os.environ['WARNING_DAYS'])
OVERDUE_DAYS = int(os.environ['OVERDUE_DAYS'])
DEACTIVATE_DAYS = int(os.environ['DEACTIVATE_DAYS'])
DELETION_DAYS = int(os.environ['DELETION_DAYS'])

s3 = boto3.client('s3')
iam = boto3.client('iam') 
ses = boto3.client('ses', region_name=SES_REGION) 

email_template = {
  "30_days_warning": {
    "subject": "Your AWS Access Key Has Reached The Warning Period.",
    "body": "Your current AWS access key age has reached the warning period. Please take time to create and use new access key then delete this current key. "
  },
  "new_access_key": {
    "subject": "New AWS Access Key has been issued to your IAM User Account",
    "body": "Your current AWS access key age is over the allowed number of active days. It will soon be deactivated and removed automatically.\nPlease download and use your new access key credentials. "
  },
  "deactivate_old_key": {
    "subject": "Old AWS Access Key has been deactivated in your your IAM User Account",
    "body": "Your old AWS access key age is over the allowed number of active days. So it has been deactivated and will soon be deleted automatically. \nYou don't need to take any action for this email."
  },
  "delete_old_key": {
    "subject": "Old AWS Access Key has been deleted in your your IAM User Account",
    "body": "Your old AWS access key age is over the allowed number of inactive days. So it has been deleted already. \nYou don't need to take any action for this email."
  }
}

# Send Notification Email via SES
def send_noti_email(user_email, subject, body):
  ses.send_email(
    Source=SES_EMAIL,
    Destination={'ToAddresses': [user_email]},
    Message={'Subject': {'Data': (subject)}, 'Body': {'Text': {'Data': body}}}
  )
  print("Done sending email")


# Check Access Key ID Creation Day with Current Date
def key_age_check(date_time):
  converted_dt = date_time.date() 
  time_diff = (TODAY - converted_dt).days
  return time_diff

# Check User Tag and Return Value
def get_user_tag(user_name, tag_name):
  user_info = iam.get_user(UserName=user_name)['User']
  result = False
  if "Tags" in user_info:
    for tag in user_info['Tags']: 
      if tag['Key'] == tag_name: 
        result = tag['Value']
        break
  return result


# # Delete User Key if its status is Inactive and hasn't been used once (or hasn't been used for so long)
# def del_unused_inactive_key(user_name, access_key_id):
#   resp = iam.get_access_key_last_used(AccessKeyId=access_key_id)
#   if "LastUsedDate" not in resp['AccessKeyLastUsed']:
#     print("This key has never been used and being inactive. So it will be removed. ")
#     iam.delete_access_key(UserName=user_name,AccessKeyId=access_key_id)
#   if key_age_check(resp['LastUsedDate']) > 30: 
#     print("This key hasn't been used more than 30 days and being inactive. So it will be removed. ")
#     iam.delete_access_key(UserName=user_name,AccessKeyId=access_key_id)


# Upload Secrets as File to S3 Bucket - To improve security, the Bucket Policy can set permissions based 
# on prefix to only allow that user to access
def upload_cred_to_s3(user_name, access_key_id, secret_access_key):
  file_name = user_name + "_" + access_key_id + ".csv"
  file = open("/tmp/" + file_name, "w") 
  file.write(f"UserName,AccessKeyId,SecretAccessKey\n{user_name},{access_key_id},{secret_access_key}")
  file.close()
  obj_name = "credential/" + user_name + "/" + file_name
  s3.upload_file("/tmp/" + file_name, S3_CSV_BUCKET, obj_name)
  os.remove("/tmp/" + file_name)
  return f"{S3_CSV_BUCKET}/{obj_name}"


### Main Lambda Function
def lambda_handler(event, context): 
  try:
    # Get all users and iterate over all
    user_list = iam.list_users()['Users']
    for user in user_list:
      user_name = user['UserName']
      print(user_name)

      ## Check and Get User's Email Tag. Continue to next user if has no "email" tag
      if get_user_tag(user_name, IAM_EMAIL_TAG_KEY) is False:
        print("This user has no email tag.")
        continue
      else: 
        user_email = get_user_tag(user_name, IAM_EMAIL_TAG_KEY)
      print(user_email)
      
      ## Check if User was checked by this function previously and have an added LAST_CHECK_DATE_TAG_KEY key tag
      if get_user_tag(user_name, LAST_CHECK_DATE_TAG_KEY) is False: 
          user_access_keys_list = iam.list_access_keys(UserName=user_name)['AccessKeyMetadata']

          ### Check if User already has 2 active keys - Send Warning Email only
          if len(user_access_keys_list) == MAX_KEYS_PER_USER and all(key['Status'] == "Active" for key in user_access_keys_list): 
              print("2 keys 2 active")
              for access_key in user_access_keys_list:
                access_key_id = access_key['AccessKeyId']
                if key_age_check(access_key['CreateDate']) > WARNING_DAYS:   # Get Access Key Age and check if it is older than 30 days
                  print("Access Key ID " + access_key_id + " of User " + user_name + " has reached the warning period")

                  #### Send Notification
                  email_body = f"Current Access Key: {access_key_id}\n" + email_template['30_days_warning']['body']
                  send_noti_email(user_email, email_template['30_days_warning']['subject'], email_body)
          
          ### Check if User has 1 active key and 1 inactive key - Send Warning Email and Recommend to delete inactive key
          elif len(user_access_keys_list) == MAX_KEYS_PER_USER and any(key['Status'] == "Inactive" for key in user_access_keys_list): 
              print("2 keys 1 active")
              for access_key in user_access_keys_list:
                access_key_id = access_key['AccessKeyId']
                if access_key['Status'] == "Active" and key_age_check(access_key['CreateDate']) > WARNING_DAYS:
                  print("Access Key ID " + access_key_id + " of User " + user_name + " has reached the warning period")

                  #### Send Notification
                  additional_note = "\nThe system is unable to create new key for you since you already have an existing Inactive Access Key.\nPlease take time to remove it in AWS Console/your IAM User Account/Security credential tab/Access keys section."
                  email_body = f"Current Access Key: {access_key_id}\n" + email_template['30_days_warning']['body'] + additional_note
                  send_noti_email(user_email, email_template['30_days_warning']['subject'], email_body)

                # # Uncomment only when you want to remove Unused Inactive Key or Inactive that hasn't been used more than 30 days
                # elif access_key['Status'] == "Inactive":
                #   del_unused_inactive_key(user_name, access_key_id)

          ### Check if User has 1 active key only
          elif len(user_access_keys_list) == 1 and user_access_keys_list[0]['Status'] == "Active":
              print("1 key 1 active")
              access_key = user_access_keys_list[0]
              access_key_id = access_key['AccessKeyId']
              
              #### Check if key age is over allowed number of days
              if access_key['Status'] == "Active" and key_age_check(access_key['CreateDate']) > OVERDUE_DAYS:
                print("Access Key ID " + access_key_id + " of User " + user_name + " is over the allowed number of active days")

                #### Create New Access Key and Upload to S3 Bucket
                credential = iam.create_access_key(UserName=user_name)
                object_path = upload_cred_to_s3(user_name, credential['AccessKey']['AccessKeyId'], credential['AccessKey']['SecretAccessKey'])
                print("New key has been issued")

                #### Send Email instruction to download new key.
                instruction =f"\nDownload via CLI: 'aws s3 cp s3://{object_path} ./'\nDownload via Console Link: https://s3.console.aws.amazon.com/s3/object/{object_path}"
                email_body = email_template['new_access_key']['body'] + instruction
                send_noti_email(user_email, email_template['new_access_key']['subject'], email_body)
                
                #### Add Tags to let the function knows to check/disable/delete the old key next time
                iam.tag_user(UserName=user_name,Tags=[{'Key': LAST_CHECK_DATE_TAG_KEY,'Value': str(TODAY)}]) 
                iam.tag_user(UserName=user_name,Tags=[{'Key': LAST_CHECK_OLD_KEY_TAG_KEY,'Value': access_key_id}])
                
              #### Check if key age is in warning period
              elif access_key['Status'] == "Active" and key_age_check(access_key['CreateDate']) > WARNING_DAYS:
                print("Access Key ID " + access_key_id + " of User " + user_name + " has reached the warning period")
                email_body = f"Current Access Key: {access_key_id}\n" + email_template['30_days_warning']['body']
                send_noti_email(user_email, email_template['30_days_warning']['subject'], email_body)

          else: 
              print("This user has no active key to check")
        
      ## User already has LAST_CHECK_DATE_TAG_KEY tag key (Which means new key has been issued by this function already)
      else:
          user_access_keys_list = iam.list_access_keys(UserName=user_name)['AccessKeyMetadata']
          last_check_date = datetime.datetime.strptime(get_user_tag(user_name, LAST_CHECK_DATE_TAG_KEY).strip(), "%Y-%m-%d") 
          last_check_old_key = get_user_tag(user_name, LAST_CHECK_OLD_KEY_TAG_KEY)

          ### Check if the old key is over the allowed active days after new key has been issued
          if len(user_access_keys_list) == MAX_KEYS_PER_USER and all(key['Status'] == "Active" for key in user_access_keys_list):
              if key_age_check(last_check_date) > DEACTIVATE_DAYS:
                iam.update_access_key(UserName=user_name, AccessKeyId=last_check_old_key, Status="Inactive")   # Make Inactive/Disable Key
                iam.tag_user(UserName=user_name,Tags=[{'Key': LAST_CHECK_DATE_TAG_KEY,'Value': str(TODAY)}]) 
                print(f"Old key {last_check_old_key} has been made Inactive.") 

                #### Send Notification Email
                email_body = f"Old Access Key: {last_check_old_key}\n" + email_template['deactivate_old_key']['body']
                send_noti_email(user_email, email_template['deactivate_old_key']['subject'], email_body)

              else: 
                print(f"Old key {last_check_old_key} age hasn't reached its allowed active days")
          
          ### Check if the deactivated key is over the allowed inactive days
          elif len(user_access_keys_list) == MAX_KEYS_PER_USER and any(key['Status'] == "Inactive" for key in user_access_keys_list):
              if key_age_check(last_check_date) > DELETION_DAYS:
                iam.delete_access_key(UserName=user_name, AccessKeyId=last_check_old_key)
                iam.untag_user(UserName=user_name, TagKeys=[ LAST_CHECK_DATE_TAG_KEY, LAST_CHECK_OLD_KEY_TAG_KEY ])
                print(f"Inactivated key {last_check_old_key} has been deleted.")

                #### Send Notification Email
                email_body = f"Old Access Key: {last_check_old_key}\n" + email_template['delete_old_key']['body']
                send_noti_email(user_email, email_template['delete_old_key']['subject'], email_body)

              else: 
                print(f"Inactivated key {last_check_old_key} age hasn't reached its allowed inactive days")

          else: 
              print("NotFoundException: Something went wrong. There should be 2 keys. If there's only 1 key left, last-check-date tag should not be here.\nEither user has deleted the key by him/herself or the function has made a mistake.")
              iam.untag_user(UserName=user_name, TagKeys=[ LAST_CHECK_DATE_TAG_KEY, LAST_CHECK_OLD_KEY_TAG_KEY ])
              print("Unnecessary tags have been removed for the function to work properly next time.")

  except ClientError as err:
    print(err.response['Error']['Message'])

  except Exception as err:
    print(err)