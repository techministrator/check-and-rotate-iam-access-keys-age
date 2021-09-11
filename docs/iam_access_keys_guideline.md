# IAM Access Keys Guideline

The guideline below should be followed in order to keep the system as secure as possible in nowadays. 

## Best Practices
- Avoid storing access keys in plaintext in any public repository (Ex: GitHub), online drive, website, etc. 
- Do not share your IAM User account access keys to anyone. If you wish to use a shared access key with a team, please ask the administrator to create a bot user and provide that account the least possible and sufficient permissions.
- Remove unnecessary or unused access keys
- Rotate access keys regularly
- If you have no task that requires to use access key or don't think you need one. Please remove all keys currently in your IAM User Account. 


## General Rules and Guideline

For the above tips, the below is the recommended approach for you to do so and how the system can automate it.
- If you have 2 Active access keys. Please choose the newest one and remove the other. 

- If you have 1 Active access key and 1 Inactive access key. Please remove the Inactive one. 

- If you have only 1 active access key. This is a desired expectation in the system. You just need to pay attention to the following: 
  - After 30 days usage of the active key, the system will send you a warning email recommending to rotate your key (create new key and remove the warning one). If you have time please proactively do this by yourself. This is the most secure way. You will get reminders after a few days if you forget to rotate. 
  
  - After 60 days usage of the active key (because you don't have time to create new one or any other reason), the system will automatically create a new one for you and send the instruction to download the **new key** for you (the file will be stored in S3 bucket folder that only you can access the file). Please do delete the file after you download it to keep your credential secure as much as possible. Your current key will be marked as "**old key**" and will be removed soon. You can login the console and delete the key by yourself if you wish. Otherwise, the system will perform the following for you. 
  
    - After 10 days since you're provisioned a **new key**, the **old key** will be deactivated/made inactive automatically by the system. If suddenly, you can't run any command or call to any AWS APIs. It's likely that you haven't checked and used the new key. If this happens, be sure to login the AWS management console and create a new key for you. Because the credential file is probably deleted already. Don't attempt to reactivate/make it active again. This key age is over the allowed active days already which is insecure to continue using it. 
  
    - After 10 days since your **old key** is deactivated, it will be deleted automatically by the system. In this case, your IAM User account only have 1 access key left which is the one you have been using.
  
- If you have no access key. The system does nothing to you and you won't receive any notification. 
