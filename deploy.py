import subprocess
import pipreqs
import boto3
import yaml
import sys
import os
import json
from pathlib import Path

lambda_client = boto3.client('lambda', 'ap-northeast-2')
iam_client = boto3.client('iam')
api_client = boto3.client('apigatewayv2', 'ap-northeast-2')
event_client = boto3.client('events', 'ap-northeast-2')
account_id = boto3.client('sts').get_caller_identity().get('Account')


def run(ls):
    print(f"Running: {ls}")
    return subprocess.run(ls, check=True, universal_newlines=True, shell=True)


# https://stackoverflow.com/a/51950538
def copy_files_to_tmp_dir(script_file, config_file, template_data):
    run('rm -rf ./.tmp_lambda')
    run('mkdir ./.tmp_lambda')
    if not script_file is None:
        run(f'cp {Path(config_file).parent.absolute()}/{script_file} ./.tmp_lambda/main.py')
    run(f'cp {config_file} ./.tmp_lambda/config.yml')
    file_path = Path(__file__).parent.absolute()
    os.chdir('.tmp_lambda')
    run(f'cp {file_path}/lambda_function.py lambda_function.py')
    if template_data is not None:
        run(f'cp {file_path}/template/{template_data["type"]}.py template.py')


def register_requirements_in_txt():
    run('pipreqs .')


def install_requirements():
    run('pip3 install -r requirements.txt -t .')


def create_zip_file():
    run('zip -qr zipped.zip *')


def create_iam_role():
    # TODO: 이게 도대체 어떤 역할을 하는건지 연구해보기
    assumed = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": ["lambda.amazonaws.com"]
                },
                "Action": ["sts:AssumeRole"]
            }
        ]
    }
    try:
        iam_client.create_role(
            RoleName='auto-lambda-role',
            AssumeRolePolicyDocument=json.dumps(assumed))
    except iam_client.exceptions.EntityAlreadyExistsException:
        pass
    # TODO 좀 덜 general하게 설정하기
    return iam_client.attach_role_policy(RoleName='auto-lambda-role', PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess')


def create_lambda(lambda_name):
    with open('zipped.zip', 'rb') as o:
        zipfile = o.read()
    try:
        return lambda_client.create_function(
            FunctionName=lambda_name,
            Runtime='python3.8',
            Handler='lambda_function.lambda_handler',
            Role=f'arn:aws:iam::{account_id}:role/auto-lambda-role',
            Code={'ZipFile': zipfile}
        )
    except lambda_client.exceptions.ResourceConflictException:
        return None


def upload_code_to_lambda(lambda_name):
    with open('zipped.zip', 'rb') as o:
        zipfile = o.read()
    response = lambda_client.update_function_code(
        FunctionName=lambda_name,
        ZipFile=zipfile
    )
    return response


def register_api_gateway(lambda_name):
    client_body = {
        "openapi": "3.0.0",
        "info": {
            "title": f"{lambda_name}-API",
            "description": "Created by AutoLambda",
            "version": ""
        },
        "paths": {
            f"/{lambda_name}": {
                "x-amazon-apigateway-any-method": {
                    "x-amazon-apigateway-integration": {
                        "type": "aws_proxy",
                        "uri": f"arn:aws:lambda:ap-northeast-2:{account_id}:function:{lambda_name}",
                        "payloadFormatVersion": "2.0"
                    }
                }
            }
        }
    }
    import_result = api_client.import_api(
        Body=json.dumps(client_body)
    )
    print(f'Api Import Result = {import_result}')
    api_client.create_stage(
        ApiId=import_result['ApiId'],
        StageName='$default',
        AutoDeploy=True
    )
    lambda_client.add_permission(
        FunctionName=lambda_name,
        StatementId="AutoLambda-Api-Permission-Statement",
        Action="lambda:InvokeFunction",
        Principal="apigateway.amazonaws.com",
        SourceArn=f"arn:aws:execute-api:ap-northeast-2:{account_id}:{import_result['ApiId']}/*/*/{lambda_name}"
    )
    return f'{import_result["ApiEndpoint"]}/{lambda_name}'


def find_lambda_policy_statement(lambda_name, statement_id):
    try:
        statements = json.loads(lambda_client.get_policy(
            FunctionName=lambda_name)['Policy'])['Statement']
        return next((i for i in statements if i['Sid'] == statement_id), None)
    except lambda_client.exceptions.ResourceNotFoundException:
        # lambda가 있지만 trigger가 없어도 여기로 떨어짐.
        # lambda가 실제로 없는 경우도 구분할 수 있어야 할까? 지금은 없어 보인다.
        return None


def find_registered_api(lambda_name):
    registered = find_lambda_policy_statement(
        lambda_name,  "AutoLambda-Api-Permission-Statement")
    if registered is None:
        return None
    print(registered)
    api_id = registered['Condition']['ArnLike']['AWS:SourceArn'].split(':')[
        5].split('/')[0]  # FIXME: ..??
    return f'https://{api_id}.execute-api.ap-northeast-2.amazonaws.com/{lambda_name}'


def register_cloudwatch_event(lambda_name, minutes):
    if not (isinstance(minutes, int) and (minutes >= 1 or minutes == -1)):
        raise ValueError(
            "minute should be integer that is -1 or larger than 0")
    rule_name = f'AutoLambda-{lambda_name}-rule'
    if minutes == -1:
        print('minutes == -1, deleting rule if exists')
        try:
            event_client.remove_targets(
                Rule=rule_name,
                Ids=[
                    'AutoLambda-Target'
                ]
            )
        except event_client.exceptions.ResourceNotFoundException:
            pass
        try:
            lambda_client.remove_permission(
                FunctionName=lambda_name,
                StatementId='AutoLambda-Event-Permission-Statement'
            )
        except lambda_client.exceptions.ResourceNotFoundException:
            pass
        event_client.delete_rule(Name=rule_name)  # rule은 없어도 exception이 안나더라
        return
    schedule_expression = f'rate({minutes} {"minute" if minutes == 1 else "minutes"})'
    print('Schedule expression is', schedule_expression)
    rule_arn = event_client.put_rule(
        Name=rule_name,
        Description=f'Rule created by AutoLambda',
        ScheduleExpression=schedule_expression,
        State='ENABLED'
    )['RuleArn']
    try:
        lambda_client.add_permission(
            FunctionName=lambda_name,
            StatementId='AutoLambda-Event-Permission-Statement',
            Action='lambda:InvokeFunction',
            Principal='events.amazonaws.com',
            SourceArn=rule_arn
        )
    except lambda_client.exceptions.ResourceConflictException:
        # 이미 permission이 추가된 상태.
        # 이 함수에서 사용한 put_rule, put_targets는 모두 업데이트도 할 수 있어서 별도의 예외처리가 없음
        pass
    event_client.put_targets(
        Rule=rule_name,
        Targets=[{
            'Id': 'AutoLambda-Target',
            'Arn': f'arn:aws:lambda:ap-northeast-2:{account_id}:function:{lambda_name}'
        }]
    )
    return rule_arn


def cleanup():
    os.chdir('..')
    run('rm -rf .tmp_lambda')


def main(config_file):
    with open(config_file) as o:
        cfg = yaml.load(o, Loader=yaml.SafeLoader)
    lambda_name = cfg['lambda_name']
    schedule_rate = cfg.get('schedule_rate', -1)
    script_file = cfg.get('script_file')
    print('Copying files..')
    copy_files_to_tmp_dir(script_file, config_file, cfg.get('template'))
    # Maybe we can test the script here
    print('Generating requirements.txt..')
    register_requirements_in_txt()
    print('Downloading requirements..')
    install_requirements()
    print('Creating zip file..')
    create_zip_file()
    print('Try creating IAM Role..')
    print(create_iam_role())
    print('try creating lambda..')
    create_lambda_result = create_lambda(lambda_name)
    if create_lambda_result is None:
        print('Lambda already exists. Uploading..')
        lambda_upload_result = upload_code_to_lambda(lambda_name)
        print(lambda_upload_result)
    else:
        print('Lambda successfully created.')
    print('Finding registered API..')
    api_url = find_registered_api(lambda_name)
    if api_url is None:
        print('Could not find API. Registering new API Gateway..')
        api_url = register_api_gateway(lambda_name)
    print(f'Endpoint is {api_url}')
    print('Registering cloudwatch events..')
    print(
        f'RuleArn is {register_cloudwatch_event(lambda_name, schedule_rate)}')
    print('Cleanup..')
    cleanup()
    print('Done.')


if __name__ == '__main__':
    if len(sys.argv) == 1:
        main('config.yml')
    else:
        main(sys.argv[1])
