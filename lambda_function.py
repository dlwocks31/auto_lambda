import importlib
import json
import sys


from requests import get, post
import boto3
import yaml
from decouple import config

# https://aws.amazon.com/ko/premiumsupport/knowledge-center/build-python-lambda-deployment-package/
# python3 -m pip install requests -t ./
with open("config.yml") as o:
    cfg = yaml.load(o, Loader=yaml.SafeLoader)
url = cfg['slack_url']
lambda_name = cfg['lambda_name']
filename = f'{lambda_name}.txt'
bucketname = 'auto-lambda'
s3 = boto3.resource('s3')
s3_client = boto3.client('s3')


def is_data_different(old_data, new_data):
    return old_data != new_data


def serialize_data(data):
    return json.dumps(data)


def deserialize_data(serialized):
    return json.loads(serialized)


def fetch_data():
    template = cfg.get('template')
    if template:
        # template폴더 안에있으면 전부 fetch_data가 있어야됨
        fetch_data = __import__('template').fetch_data
        return fetch_data(**template)
    raise Exception(
        'fetch_data must be overwritten, if no template type specified')


def format_data(data, old_data):
    return f'old data: {old_data}\nnew data: {data}'


try:
    overriding_func = ['is_data_different', 'serialize_data',
                       'deserialize_data', 'fetch_data', 'format_data']
    main_module = importlib.import_module('main')
    for fun in overriding_func:
        if fun in dir(main_module):
            setattr(sys.modules[__name__], fun, getattr(main_module, fun))
except ModuleNotFoundError:
    pass


def upload_data(data):
    return s3_client.put_object(Body=serialize_data(data).encode('utf-8'), Bucket=bucketname, Key=filename)


def download_data():
    try:
        return deserialize_data(s3.Object(bucketname, filename).get()['Body'].read().decode('utf-8'))
    except s3_client.exceptions.NoSuchKey:
        return None
    except s3_client.exceptions.NoSuchBucket:
        s3_client.create_bucket(Bucket=bucketname, CreateBucketConfiguration={
            'LocationConstraint': 'ap-northeast-2',
        },)
        return None


def send_slack(message):
    return post(url, json={'text': message})


def main():
    data = fetch_data()
    old_data = download_data()
    if data != old_data:
        upload_data(data)
        text = format_data(data, old_data)
        resp = send_slack(text)
        return [resp.status_code, text]
    else:
        return [200, 'EQUAL']


def lambda_handler(event, context):
    try:
        result = main()
        print(result)
        return {
            'statusCode': result[0],
            'body': f'Status code = {result[0]}.\n{result[1]}'
        }
    except Exception as e:
        send_slack(str(e))
        raise e


if __name__ == '__main__':
    lambda_handler(None, None)
