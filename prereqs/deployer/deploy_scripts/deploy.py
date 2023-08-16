#! /usr/bin/env python3
# encoding: utf-8
"""
Author: @awsthiya

deploy.py provides automated quick start capability 
for the developers to deploy the Organization Unit Level
Stack Set deployment.

This python module takes below inputs

1. Environment (current environment name)
2. Current AWS Region (region where pipeline is running)
3. Artifacts S3 Bucket (to store the CloudFormation Template for stack set)
"""

import os
import sys
import argparse
import stackset_deployer
import logging
import boto3
from botocore.exceptions import ClientError

FORMAT = '%(asctime)s %(levelname)s %(message)s'
logging.basicConfig(format=FORMAT,
                    datefmt="%Y-%m-%d %H:%M:%S",
                    handlers=[logging.StreamHandler(sys.stdout)]
                    )
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

class AutoDeployer:
    def __init__(self, env, region, s3_bucket, app_name):
        self.env = env
        self.aws_region = region
        self.artifact_bucket = s3_bucket
        self.app_name = app_name
        self.template_path = f"{os.getcwd()}/templates/"
        self.template_parameters_path = f"{os.getcwd()}/parameters/"
        self.deployment_config_file = f"{os.getcwd()}/deploy_configs/deployment_config.json"
        self.s3_resource = boto3.resource('s3', self.aws_region)

    def check_config_exists(self):
        """
        This method checks if the config file exists in the default configuration folder
        """
        if os.path.exists(self.deployment_config_file):
            LOGGER.info("Deployment Config file found")
        else:
            error_msg = f"Deployment config file not found in {self.deployment_config_file}"
            raise Exception(error_msg)

    def get_templates(self):
        """
        This method finds the list of valid CloudFormation Templates and its 
        Parameter files provided in their respective default directories.
        """
        try:
            LOGGER.info("Checking for valid CloudFormation Templates and its parameter files")
            app_templates = os.listdir(self.template_path)
            app_template_parameters = os.listdir(self.template_parameters_path)
            templates = list()
            parameter_identifier = f"-parameter-{self.env}.json"

            default_templates = ['template.yml', 
                                'template.yaml']
            default_template_parameters = ['template-parameter-dev.json', 
                                        'template-parameter-test.json', 
                                        'template-parameter-prod.json']

            if default_templates in app_templates:
                raise Exception("Change the Name of CloudFormaiton Template as <application name>.yml, default template.yml or template.yaml are not allowed")

            if default_template_parameters in app_template_parameters:
                raise Exception("Change the Name of Template Parameter file as <application name>-parameter-<evn>.json with, default names are not allowed")

            valid_templates = [ filename for filename in app_templates if filename.endswith(".yaml") or filename.endswith(".yml")]
            valid_template_parameters = [ filename for filename in app_template_parameters if filename.endswith(".json")]

            for template in valid_templates:
                template_name = os.path.splitext(template)[0]
                for parameter_file in valid_template_parameters:
                    if template_name == parameter_file.replace(parameter_identifier,''):
                        deployer_input = (template, parameter_file)
                        templates.append(deployer_input)
                
            if templates:
                return templates
            else:
                raise Exception(f"No valid CloudFormation Template and its Parameter File found for {self.env} environment")

        except Exception as excep:
            error_msg = f"Error while trying to get the templates, {str(excep)}"
            raise Exception(error_msg)

    def stage_cloudformation_template(self, app_name, template_file):
        """
        This method uploads the CloudFormation Template file to 
        Artifacts S3 bucket and returns HTTPS URL for the file.
        """
        try:
            s3_key = f"template/{app_name}/{template_file}"
            source_file = f"{self.template_path}{template_file}"
            _ = self.s3_resource.meta.client.upload_file(Bucket=self.artifact_bucket,
                                                        Key=s3_key,
                                                        Filename=source_file)
            template_https_url = f"https://{self.artifact_bucket}.s3.amazonaws.com/{s3_key}"
            return template_https_url
        except Exception as excep:
            error_msg = f"Error while trying to upload the template {template_file} to S3 bucket {self.artifact_bucket}, {str(excep)}"
            raise Exception(error_msg)

    def deploy(self):
        """
        This method gets all the valid CloudFormation Templates and its 
        Parameter files provided and triggers the stack set deployment
        for each template.
        """
        try:
            LOGGER.info("Auto Deployment Starts")
            LOGGER.info(f"CloudFormaiton Templates are excepted in {self.template_path}")
            LOGGER.info(f"Parameter files for the CloudFormation Templates are expected in {self.template_parameters_path}")
            LOGGER.info(f"Deployment Configuration file used for this deployment {self.deployment_config_file}")

            self.check_config_exists()
            templates = self.get_templates()
            ss_deployer = stackset_deployer.Deployer(self.env, self.aws_region)

            for template in templates:
                template_url = self.stage_cloudformation_template(self.app_name, template[0])
                parameter_file = f"{self.template_parameters_path}{template[1]}"
                ss_deployer.processor(template_url, parameter_file, self.deployment_config_file)

            LOGGER.info("Auto Deployment Starts")
        except Exception as excep:
            error_msg = f"Auto Deployment Process Failed: {str(excep)}"
            LOGGER.error(error_msg)
            raise


def main(args):
    """
    This is main function triggers the Automated Deployment process
    """
    environment = args.env
    region = args.region
    s3_bucket = args.s3_bucket
    app_name = args.app_name

    auto_deployer = AutoDeployer(environment, region, s3_bucket, app_name)
    auto_deployer.deploy()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(prog='deploy.py',
                                     usage='%(prog)s --env <environment> --region <aws region> --s3_bucket <artifact s3 bucket> --app_name <repository/app name>',
                                     description="Delegated Admin Service Managed Stack Set Automated Deployer")
    parser.add_argument('--env',
                        action='store',
                        type=str,
                        required=True)
    parser.add_argument('--region',
                        action='store',
                        type=str,
                        required=True)
    parser.add_argument('--s3_bucket',
                        action='store',
                        type=str,
                        required=True)
    parser.add_argument('--app_name',
                        action='store',
                        type=str,
                        required=True)
    arguments = parser.parse_args()
    sys.path.append(os.path.dirname(__file__))
    main(arguments)
