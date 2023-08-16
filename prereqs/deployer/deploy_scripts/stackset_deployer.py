#! /usr/bin/env python3
# encoding: utf-8
"""
Author: @awsthiya

stackset_deploy.py is the stack set deployer which assess the input
configuration and deploys or deletes the stack sets.

This moudle evaluates the deployment target inputs provided in the deployment config
file and performs the stack set deployment.
"""

import os
import sys
import json
import argparse
from time import sleep
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


class Deployer:
    def __init__(self, env, aws_region):
        self.environment = env
        self.cf_client = boto3.client('cloudformation', aws_region)
        self.deployment_configs = None

    def get_boto_api_paginator(self, client, method, op_parameters):
        """
        This method returns the boto3 paginator
        """
        paginator = client.get_paginator(method)
        iterator = paginator.paginate(**op_parameters)
        return iterator

    def get_current_stacksets(self):
        """
        This method returns the list of current stack sets
        """
        try:
            current_stack_sets = []
            stackset_filter = {
                                "Status": "ACTIVE",
                                "CallAs": "DELEGATED_ADMIN"
                            }
            stackset_paginator = self.get_boto_api_paginator(self.cf_client,
                                                            'list_stack_sets',
                                                            stackset_filter)
            for stackset_page in stackset_paginator:
                current_stack_sets = current_stack_sets + [stackset['StackSetName'] for stackset in stackset_page['Summaries']]

            return current_stack_sets          
        except Exception as excep:
            error_msg = f"Error while getting current list of stack sets: {str(excep)}"
            raise Exception(error_msg)

    def check_stackset_exists(self, stackset_name):
        """
        This method check the supplied stack set exists or not
        """
        LOGGER.info(f"Checking the existence of {stackset_name} stack set")
        return stackset_name in self.get_current_stacksets()

    def get_stack_instances(self, stackset_name):
        """
        This method returns the listo f stack instances of the supplied
        stack set
        """
        try: 
            current_stack_instances = []
            stack_instances_filter = {
                                        "StackSetName": stackset_name,
                                        "CallAs": "DELEGATED_ADMIN"
                                    }
            stack_instances_paginator = self.get_boto_api_paginator(self.cf_client,
                                                                    'list_stack_instances',
                                                                    stack_instances_filter)
            for stack_instances_page in stack_instances_paginator:
                for stack_instance in stack_instances_page['Summaries']:
                    current_stack_instance = {
                                                'StackSetId': stack_instance['StackSetId'],
                                                'StackId': stack_instance.get('StackId', None),
                                                'DeployedRegion': stack_instance['Region'],
                                                'DeployedOUId': stack_instance['OrganizationalUnitId'],
                                                'DeployedAccount': stack_instance['Account'],
                                                'InstanceSyncStatus': stack_instance['Status'],
                                                'StackInstanceStatus': stack_instance['StackInstanceStatus']['DetailedStatus']
                                            }
                    current_stack_instances.append(current_stack_instance)
            
            return current_stack_instances
        except Exception as excep:
            error_msg = f"Error while getting current list of stack instances for the stack set {stackset_name}: {str(excep)}"
            raise Exception(error_msg)

    def get_stack_instances_current_regions(self, stack_instances):
        """
        This method returns the list of stack instances in current region
        """
        stack_instances_current_regions = [stack_instance["DeployedRegion"] for stack_instance in stack_instances]
        return list(set(stack_instances_current_regions))

    def get_stack_instances_current_ous(self, stack_instances):
        """
        This method returns the currently deployed Organization Units of 
        supplied stack instances
        """
        stack_instances_current_ous = [stack_instance["DeployedOUId"] for stack_instance in stack_instances]
        return list(set(stack_instances_current_ous))
    
    def get_stack_instances_status(self, stack_instances):
        """
        This method returns the status of supplied stack instances
        """
        stack_instances_status = [stack_instance["StackInstanceStatus"] for stack_instance in stack_instances]
        return list(set(stack_instances_status))
    
    def check_stack_instances_progress(self, stackset_name):
        """
        This method checks the current progress status of 
        stack instances of supplied stack set
        """
        try: 
            check_status = True
            progress_status = ['PENDING', 'RUNNING']
            while check_status:
                stack_instances = self.get_stack_instances(stackset_name)
                stack_instances_status = self.get_stack_instances_status(stack_instances)
                check_status = any(status in progress_status for status in stack_instances_status)
                for stack_instance in stack_instances:
                    LOGGER.info(f"StackId: {stack_instance['StackId']} - OU: {stack_instance['DeployedOUId']} \
                                    - Region: {stack_instance['DeployedRegion']} - Status: {stack_instance['StackInstanceStatus']}")

            return stack_instances
        except Exception as excep:
            error_msg = f"Error while checking stack instance progress for the stack set {stackset_name}: {str(excep)}"
            raise Exception(error_msg)

    def check_stack_instances_opeartion_status(self, operation_id, stackset_name):
        """
        This method checks the opeartion status of supplied stack set and operation id
        """
        try: 
            current_op_status = "RUNNING"
            pending_op_status = ['RUNNING', 'STOPPING']

            while current_op_status in pending_op_status:
                operation = self.cf_client.describe_stack_set_operation(StackSetName=stackset_name,
                                                                        OperationId=operation_id,
                                                                        CallAs='DELEGATED_ADMIN')
                current_op_status = operation['StackSetOperation']['Status']
                current_op_action = operation['StackSetOperation']['Action']

                LOGGER.info(f"Checking {current_op_action} opeartion ({operation_id}) status of the stack set {stackset_name} - {current_op_status}")
                sleep(15)

            return current_op_status
        except Exception as excep:
            error_msg = f"Error while checking operation status for the stack set {stackset_name} and operation ID {operation_id}: {str(excep)}"
            raise Exception(error_msg)

    def get_tags(self):
        """
        This method returns the default tags for the stack set
        """
        tags = [ 
                    {
                        "Key": "Stack_Set_Owner",
                        "Value": "Data Platform Team"
                    }

               ]
        return tags

    def deploy_stack_set(self, is_exists, cft_url, cft_parameters):
        """
        This method depoys the stack set; evaluates the supplied parameters
        and calls right API to create/update stack set.
        """
        try:
            auto_deployment = {
                                "Enabled": True if self.deployment_configs['auto_deployement'].lower() == "true" else False,
                                "RetainStacksOnAccountRemoval": True if self.deployment_configs['retain_stacks_on_account_removal'].lower() == "true" else False
                              }
            wait_message = ""
            completed_message = ""
            operation_id = None

            if is_exists:
                # update stack set
                LOGGER.info(f"Updating existing stack set {self.stack_set_name}")
                operational_prefs = {
                        "RegionConcurrencyType": self.deployment_configs['region_deployment_concurrency'],
                        "MaxConcurrentPercentage":self.deployment_configs['max_concurrent_percentage'],
                        "FailureTolerancePercentage":self.deployment_configs['failure_tolerance_percentage'] # ideally should be set as MaxConcurrentPercentage-1
                    }
                stack_set = self.cf_client.update_stack_set(StackSetName=self.stack_set_name,
                                                            Description=self.deployment_configs['stack_set_desciption'],
                                                            TemplateURL=cft_url,
                                                            Parameters=cft_parameters,
                                                            Capabilities=self.deployment_configs['cft_capabilities'],
                                                            Tags=self.get_tags(),
                                                            PermissionModel='SERVICE_MANAGED',
                                                            AutoDeployment=auto_deployment,
                                                            OperationPreferences=operational_prefs,
                                                            CallAs='DELEGATED_ADMIN'
                                                            )
                
                wait_message = "Waiting for stack set be updated.."
                completed_message = f"Stack set {self.stack_set_name} updated sucessfully"

                operation_id = stack_set['OperationId']                                                            

                operation_status = self.check_stack_instances_opeartion_status(operation_id, self.stack_set_name)

                if operation_status in ['FAILED', 'STOPPED']:
                    error_message = f"{self.stack_set_name} Stack Set Operation {operation_id} is {operation_status}"
                    raise Exception(error_message)
            else:
                # create stack set
                LOGGER.info(f"Creating new stack set {self.stack_set_name}")
                new_stack_set = self.cf_client.create_stack_set(StackSetName=self.stack_set_name,
                                                                Description=self.deployment_configs['stack_set_desciption'],
                                                                TemplateURL=cft_url,
                                                                Parameters=cft_parameters,
                                                                Capabilities=self.deployment_configs['cft_capabilities'],
                                                                Tags=self.get_tags(),
                                                                PermissionModel='SERVICE_MANAGED',
                                                                AutoDeployment=auto_deployment,
                                                                CallAs='DELEGATED_ADMIN',
                                                                ClientRequestToken=self.stack_set_name
                                                                )

                wait_message = "Waiting for stack set be created.."
                completed_message = f"New stack set {self.stack_set_name} created, Stack Set ID: {new_stack_set['StackSetId']}"

            while not self.check_stackset_exists(self.stack_set_name):
                LOGGER.info(wait_message)
                sleep(30)    
            
            LOGGER.info(completed_message)
            
            return True

        except Exception as excep:
            error_msg = f"Error while deploying stack set {self.stack_set_name}: {str(excep)}"
            raise Exception(error_msg)

    def deploy_stack_instances(self, operation, target_ou_ids, target_regions, filter_accounts, filter_type):
        """
        This method create/updates the stack instances into supplied
        target organization unit and regions.
        """
        try:
            deployment_targets = {
                                    "OrganizationalUnitIds": target_ou_ids
                                 }

            if filter_accounts and filter_type:
                deployment_targets["Accounts"] = filter_accounts
                deployment_targets["AccountFilterType"] = filter_type                                       
           
            operational_prefs = {
                                    "RegionConcurrencyType": self.deployment_configs['region_deployment_concurrency'],
                                    "MaxConcurrentPercentage":self.deployment_configs['max_concurrent_percentage'],
                                    "FailureTolerancePercentage":self.deployment_configs['failure_tolerance_percentage'] # ideally should be set as MaxConcurrentPercentage-1
                                }
            operation_id = None

            if operation.lower() == 'create':
                # create stack instance
                LOGGER.info(f"Creating new stack instances for the stack set {self.stack_set_name}")
                new_stack_instances = self.cf_client.create_stack_instances(StackSetName=self.stack_set_name,
                                                                            DeploymentTargets=deployment_targets,
                                                                            Regions=target_regions,
                                                                            OperationPreferences=operational_prefs,
                                                                            CallAs='DELEGATED_ADMIN')
                operation_id = new_stack_instances['OperationId']
            elif operation.lower() == 'update':
                LOGGER.info(f"Updating stack instances for the stack set {self.stack_set_name}")
                new_stack_instances = self.cf_client.create_stack_instances(StackSetName=self.stack_set_name,
                                                                            DeploymentTargets=deployment_targets,
                                                                            Regions=target_regions,
                                                                            OperationPreferences=operational_prefs,
                                                                            CallAs='DELEGATED_ADMIN')
                operation_id = new_stack_instances['OperationId']
            else:
                error_message = f"Invalid operation {operation} request"
                raise Exception(error_message)

            self.check_stack_instances_progress(self.stack_set_name)
            operation_status = self.check_stack_instances_opeartion_status(operation_id, self.stack_set_name)
            if operation_status in ['FAILED', 'STOPPED']:
                error_message = f"{self.stack_set_name} Stack Set Operation {operation_id} is {operation_status}"
                raise Exception(error_message)

            LOGGER.info(f"New stack instances for the stack set {self.stack_set_name} created")
                
        except Exception as excep:
            error_msg = f"Error while deploying stack instance for the stack set {self.stack_set_name}: {str(excep)}"
            raise Exception(error_msg)        

    def remove_stack_set(self):
        """
        This method deletes the stack set supplied
        """
        try:
            _ = self.cf_client.delete_stack_set(StackSetName=self.stack_set_name,
                                                CallAs='DELEGATED_ADMIN'
                                               )
            LOGGER.info(f"Stack Set {self.stack_set_name} has been deleted successfully!")
        
        except Exception as excep:
            error_msg = f"Error while deleting the stack set {self.stack_set_name}: {str(excep)}"
            raise Exception(error_msg)  

    def remove_stack_instances(self, target_ou_ids, target_regions):
        """
        This method delets the stack instances of the supplied stack set from
        supplied Org Unit and Region.
        """
        try:
            deployment_targets = {
                                    "OrganizationalUnitIds": target_ou_ids
                                 }
            operational_prefs = {
                                    "RegionConcurrencyType": self.deployment_configs['region_deployment_concurrency'],
                                    "MaxConcurrentPercentage":self.deployment_configs['max_concurrent_percentage'],
                                    "FailureTolerancePercentage":self.deployment_configs['failure_tolerance_percentage'] # ideally should be set as MaxConcurrentPercentage-1
                                }
            operation_id = None        
            
            remove_instances_response = self.cf_client.delete_stack_instances(StackSetName=self.stack_set_name,
                                                                              DeploymentTargets=deployment_targets,
                                                                              Regions=target_regions,
                                                                              OperationPreferences=operational_prefs,
                                                                              RetainStacks=False,
                                                                              CallAs='DELEGATED_ADMIN'
                                                                             )
            operation_id = remove_instances_response['OperationId']                                                            

            operation_status = self.check_stack_instances_opeartion_status(operation_id, self.stack_set_name)

            if operation_status in ['FAILED', 'STOPPED']:
                error_message = f"{self.stack_set_name} Stack Set Operation {operation_id} is {operation_status}"
                raise Exception(error_message)

            LOGGER.info(f"Stack instances of the stack set {self.stack_set_name} are deleted")

        except Exception as excep:
            error_msg = f"Error while deleting stack instances for the stack set {self.stack_set_name}: {str(excep)}"
            raise Exception(error_msg)      

    def get_cf_paramaters(self, input_file):
        """
        This method transforms the CloudFormation Template Parameters format
        """
        try: 
            cf_parameters = []
            with open(input_file) as file:
                parameters = json.load(file)['Parameters']
                for parameter_key in parameters.keys():
                    cf_parameter = {
                                    "ParameterKey": parameter_key,
                                    "ParameterValue": parameters[parameter_key]
                                }
                    cf_parameters.append(cf_parameter)
            
            return cf_parameters
        except Exception as excep:
            error_msg = f"Error while parsing the cloudformation parameter file {input_file}: {str(excep)}"
            raise Exception(error_msg) 

    def get_deployment_configs(self, input_file):
        """
        This method reads the deployment config file and returns the values
        as python dict.
        """
        try: 
            deployment_config = {}
            with open(input_file) as file:
                deployment_config = json.load(file)
            return deployment_config
        except Exception as excep:
            error_msg = f"Error while parsing the deployment config file {input_file}: {str(excep)}"
            raise Exception(error_msg) 

    def get_deployment_targets(self):
        """
        This method returns the deployment target details
        from deployment config based on the deployment environment.
        """
        env_key = None
        if self.environment.lower() in ['dev', 'development']:
            env_key = 'dev'
        elif self.environment.lower() in ['qa', 'test']:
            env_key = 'test'
        elif self.environment.lower() in ['prod', 'production']:
            env_key = 'prod'
        else:
            error_msg = f"Invalid value for env arguement, valid values are dev, development, qa, test, prod or production" 
            raise Exception(error_msg)

        deployment_targets = self.deployment_configs["deployment_targets"][env_key]
        tgt_deployment_ou_ids = deployment_targets.get('org_units', [])
        tgt_deployment_regions = deployment_targets.get('regions', [])
        tgt_filter_accounts = deployment_targets.get('filter_accounts', [])
        tgt_account_filter_type = deployment_targets.get('filter_type', "")

        if not (tgt_deployment_ou_ids):
            error_msg = "Organization Units is mandatory parameter supplied for deployment targets, please check deployment configuration file."
            raise Exception(error_msg) 

        return tgt_deployment_ou_ids, tgt_deployment_regions, tgt_filter_accounts, tgt_account_filter_type       

    def evaluate_deployment_targets(self, tgt_deployment_ou_ids, tgt_deployment_regions, current_ou_ids, current_regions):
        """
        This method evaluates the deployment targets for create/update/delete operations
        """
        try: 

            new_tgt_deployment_ou_ids = set(tgt_deployment_ou_ids).difference(current_ou_ids)
            new_tgt_deployment_regions = set(tgt_deployment_regions).difference(current_regions)

            undeploy_ou_ids = set(current_ou_ids).difference(tgt_deployment_ou_ids)
            undeploy_regions = set(current_regions).difference(tgt_deployment_regions)

            return list(new_tgt_deployment_ou_ids), \
                list(new_tgt_deployment_regions), \
                list(undeploy_ou_ids), \
                list(undeploy_regions)
        except Exception as excep:
            error_msg = f"Error while evaluating the deployment target configurations: {str(excep)}"
            raise Exception(error_msg) 

    def deploy(self, cft_file, cft_parameters_file):
        """
        This method performs the stack set deployment
        """
        try:
            LOGGER.info(f"Stack Set Deployment Process Initiated")
            cft_parameters = self.get_cf_paramaters(cft_parameters_file)
            is_stackset_exists = self.check_stackset_exists(self.stack_set_name)

            tgt_deployment_ou_ids, tgt_deployment_regions, tgt_filter_accounts, tgt_account_filter_type = self.get_deployment_targets()
            if is_stackset_exists:
                # updates existing stack instances and stack set
                LOGGER.info(f"Stack Set {self.stack_set_name} exists, checking for deployment target changes to apply.")
                stack_instances = self.get_stack_instances(self.stack_set_name)
                current_ous = self.get_stack_instances_current_ous(stack_instances)
                current_regions = self.get_stack_instances_current_regions(stack_instances)

                new_ous, new_regions, remove_ous, remove_regions = self.evaluate_deployment_targets(tgt_deployment_ou_ids, 
                                                                                                    tgt_deployment_regions, 
                                                                                                    current_ous, 
                                                                                                    current_regions)
                
                if (new_ous or new_regions or remove_ous or remove_regions):
                    LOGGER.info(f"Stack instances will be created/updated for Org Units, {tgt_deployment_ou_ids} and Regions, {tgt_deployment_regions}")

                    if (new_ous or new_regions):
                        LOGGER.info(f"New OUs/Regions added in deployment config.")
                        LOGGER.info(f"Stack instances will be created in Org Units, {new_ous} and Regions, {new_regions}")
                        self.deploy_stack_instances('create', 
                                                    tgt_deployment_ou_ids,
                                                    tgt_deployment_regions,
                                                    tgt_filter_accounts,
                                                    tgt_account_filter_type)
                        
                    if (remove_ous or remove_regions): 
                        LOGGER.info(f"OUs/Regions are removed in deployment config.")
                        LOGGER.info(f"Stack instances will be deleted for Org Units, {remove_ous} and regions {remove_regions}")
                        delete_orgs = []
                        delete_regions = []
                        if remove_ous:
                            delete_orgs = remove_ous
                            # delete from the requested OU from all regions
                            delete_regions = tgt_deployment_regions + remove_regions
                            LOGGER.info(f"Deleting Stack Instance for the OUs {remove_ous} and regions {delete_regions}")
                            self.remove_stack_instances(delete_orgs, delete_regions)

                        if remove_regions:
                            # delete from the requested regions from all org units
                            delete_orgs = tgt_deployment_ou_ids + delete_orgs
                            delete_regions = remove_regions
                            LOGGER.info(f"Deleting Stack Instance for the regions {remove_regions} of OUs {delete_orgs}")
                            self.remove_stack_instances(delete_orgs, delete_regions)

                LOGGER.info("Updating the stack set to deploy the CFT Changes")
                self.deploy_stack_set(is_stackset_exists, cft_file, cft_parameters)

            else:
                # create stack set and stack instance
                LOGGER.info(f"Stack set {self.stack_set_name} doesn't exists")
                self.deploy_stack_set(is_stackset_exists, cft_file, cft_parameters)
                self.deploy_stack_instances('create', 
                                            tgt_deployment_ou_ids,
                                            tgt_deployment_regions,
                                            tgt_filter_accounts,
                                            tgt_account_filter_type)
            LOGGER.info(f"Stack Set Deployment Process Completed!")
        except Exception as excep:
            error_msg = f"Error while deploying stack set {self.stack_set_name}: {str(excep)}"
            raise Exception(error_msg)        

    def undeploy(self):
        """
        This method deletes the existing stack set and instances
        froma all Org units and Regions.
        """
        try:
            LOGGER.info(f"Stack Set Deletion Process Initiated")
            is_stackset_exists = self.check_stackset_exists(self.stack_set_name)
            if is_stackset_exists:
                stack_instances = self.get_stack_instances(self.stack_set_name)
                current_ous = self.get_stack_instances_current_ous(stack_instances)
                current_regions = self.get_stack_instances_current_regions(stack_instances)
                # delete stack instances
                if current_ous and current_regions:
                    self.remove_stack_instances(current_ous, current_regions)

                # delete stack set
                self.remove_stack_set()
            else:
                error_message = f"Stack Set {self.stack_set_name} does not exists!"
                raise Exception(error_message)
            LOGGER.info(f"Stack Set Deletion Process Completed!")
        except Exception as excep:
            error_msg = f"Error while deleting stack set {self.stack_set_name}: {str(excep)}"
            raise Exception(error_msg)  

    def processor(self, cft_file, cft_parameters_file, deployment_config_file):
        """
        This method processes the stack set deployment request
        based on the values provided in deployment config file
        """
        try:
            LOGGER.info("Initiating the deployment process..")
            self.deployment_configs = self.get_deployment_configs(deployment_config_file)
            deployment_action = self.deployment_configs['deployment_action'].lower()
            self.stack_set_name = f"{self.deployment_configs['stack_set_name']}-{self.environment}"            
            
            if deployment_action == 'deploy':
                self.deploy(cft_file, cft_parameters_file)
            elif deployment_action == 'delete':
                self.undeploy()
            else:
                error_message = "Invalid deployment action provided in deployment config file. Valid options are 'deploy' and 'delete'."
                raise Exception(error_message)

            LOGGER.info("Deployment Process Completed")
        except Exception as excep:
            error_msg = f"Error in processing {self.stack_set_name}: {str(excep)}"
            LOGGER.error(error_msg)
            raise Exception(error_msg)        

