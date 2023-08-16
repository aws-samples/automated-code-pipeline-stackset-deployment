# **Data Platform - OU Level Deployment Auto CI/CD Pipeline**

The applications that needs to be deployed at Organization Unit (OU) Level must use the CloudFormation Template provided in this repository. This would create a Code Commit Repository along with deployment configuration files and scripts required for OU Level Deployment and the CI/CD Pipeline.

With this OU Level Deployment Quick Start Auto CI/CD Pipeline, developers needs to provide their CloudFormation Template and its parameter files and update the deployment configuration file for stack name and deployment targets. The deployment scripts provided by this pipeline automatically detects the CloudFormation Template and its parameter files to trigger the deployment.

- **THE MAJOR LIMITATION OF THIS AUTOMATED PIPELINE IS CUSTOMIZATION CANNOT BE DONE**
- **MULTIPLE TEMPLATES ARE NOT ALLOWED AT THE MOMENT**


## **Repository Folder Structure**

Below is the current folder structure of this repository

``` directory structure
root
├── buildspec.yml
├── cicd
│   └── cicd-pipeline.yaml
├── parameter
├── prereqs
│   ├── app_prereqs
│   │   ├── buildspec.yml
│   │   ├── deploy_configs
│   │   │   └── deployment_config.json
│   │   ├── parameters
│   │   │   ├── template-parameter-dev.json
│   │   │   ├── template-parameter-prod.json
│   │   │   └── template-parameter-test.json
│   │   └── templates
│   │       └── template.yml
│   └── deployer
│       └── deploy_scripts
│           ├── deploy.py
│           └── stackset_deployer.py
├── readme.MD
└── templates
    ├── associate-approval-rule-template.yaml
    ├── cicd-pipeline-template.yaml
    ├── cicd-role-template.yaml
    ├── lambda-template.yaml
    ├── sns-subscriptions-template.yaml
    └── sns-template.yaml 
 
```

1. **cicd** - This folder contains the cloud formation template that creates the pipeline for this repo. The pipeline will upload the application app prereqs and deployer files to an artifacts s3 bucket. The application pipeline use this artifacts for ou deployment.

2. **prereqs** - This folder contains the application artifacts and deployer files

     a. **app_prereqs** - This folder contains the artifacts that would be added into the codecommit application repository created by the stack.

     b. **deployer** - This folder contains the script files that deploys the application code and cft templates into target account for respective stage (dev, test, prod)

3. **templates** - To keep the cloudformation templates. Currently, this folder contains below cloudformation tempaltes

     - ***lambda-template.yaml*** - template used to create pre-req lambdas and lambda roles. In this case two lambdas, one lambda for associating codecommit approval rule template and second lambda for creating multiple sns subscriptions.
     - ***cicd-role-template.yaml*** - template used to create the code pipeline and code build project roles used in Application CI/CD Pipeline (one time deployment with self explanatory parameters)
     - ***cicd-pipeline-template.yaml*** - template used to create the application repository and its pipeline, refer Application CI/CD Pipeline CFT Parameters section for more details on the parameters for this template
     - ***associate-approval-rule-template.yaml*** - template to invoke custom resource that calls lambda for associating application code repo with the given codecommit approval rule template. 
     - ***sns-template.yaml*** - template to create SNS Topics used to notify the approvers (one time deployment with self explanatory parameters)
     - ***sns-subscriptions-template.yaml*** - template used to create multiple SNS subscriptions for a given SNS Topic. The subscriber email list parameter is expected as comma separated list.

lambda-template.yaml creates prerequisite functions that are invoked as custom resource (one time deployment unless update is required in function logic)
sns-template.yaml, sns-subscriptions-template.yaml and cicd-role-template.yaml templates are one deployment templates or can be deployed in case of any changes required to SNS Topics, its subscription and updates to the CI/CD related roles.

## **Application CI/CD Pipeline CFT Parameters**

1. **ApplicationName** - Specify the name of the application that would be used as name of the code commit repository and prefix the CI/CD Pipeline

2. **DeploymentConfigBucket** - Specify the Bucket Name where the deployment configuration files and script zip is stored

3. **DeploymentConfigKey** - Provide the path and zip filename (S3 Key)

4. **TemplateBucket** - Name of the S3 bucket in the CI/CD Account where the CI/CD Pipeline creation template is stored

5. **CodeBuildProjectRoleARN** - ARN of the Code Build Project Role
  
6. **CloudWatchEventRoleARN** - ARN of the CloudWatch Event Role

7. **AppRepositoryName** - Name of the Code Commit Repository created for the Application

8. **AppRepositoryDescription** - Description of the Application Code Commit Repository

9. **CodePipelineRoleARN** - ARN of the Code Pipeline Role 

10. **PRApprovalSNSARN** - ARN of the Pull Request Approval SNS Topic

11. **TESTApprovalSNSARN** - ARN of the TEST Approval SNS Topic

12. **ProdApprovalSNSARN** - ARN of the PROD Approval SNS Topic


## Application Repository Folder Structure

Application Repository will be created with below default directory structure and deployment configuration files,

``` directory structure
root
 |- deploy_configs
 |        |- deployment_config.json
 |- parameters
 |      |- template-parameter-dev.json
 |      |- template-parameter-test.json
 |      |- template-parameter-prod.json
 |- templates
 |      |- template.yml
 |- buildspec.yml
 
```

1. **deploy_configs** - contains deployment configuration file
2. **parameters** - leverage to keep the cloudformation template parameters, the parameter file name must be in the format of (template filename without extension)-parameter-(env).json. DO NOT KEEP THE DEFAULT FILE NAMES. MAINTAIN THE JSON IN SAME FORMAT PROVIDED IN THE SAMPLE FILE.
3. **templates** - leverage to keep the cloudformation template, rename the default template.yml to (application name).yml. DO NOT KEEP THE DEFAULT FILE NAMES.

**NOTE:**
**No customizations are allowed on the folder structure**

## **Script and BuildSpec**

1. **deploy.py** - This script is invoked by the buildspec.yml, which automatically finds the CloudFormation Template, its parameter files, uploads the Template to artifact S3 bucket in CI/CD Account and triggers the stack set deployment by calling stackset_deployer.py
2. **stackset_deployer.py** - This script evaluates the deployment config file and deploys (create/update/delete) the stack set and instances
3. **buildspec.yml** - This file is used by the Code Build Projects which invokes the automated quick start deployment script deploy.py to trigger the Stack Set deployment process.

## **Deployment Configuration Files**

Application developers have to provide appropriate values in deployment configuration files

**deployment_config.json** - This file is used by the deployment script which takes the values for parameters like stack set name, deployment target information etc., This file can be found under deploy_configs folder.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
