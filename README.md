# Autolambda

특정 웹 페이지의 변화를 감지하는 작업을 자동화할 수 있도록 도와줍니다.

# 작동 방식

원하는 외부 웹페이지에서 정보를 가져온 후, 만약 이번에 가져온 정보가 저번에 가져온 정보와 다르다면 이를 설정된 슬랙 채널로 알려줍니다. 조금 더 구체적으로 설명하자면:

- 어떤 웹페이지에서 어떤 정보를 가져와 비교할 것인지는 YAML파일/Pyhon 스크립트를 작성해 설정할 수 있습니다.
- 코드는 AWS Lambda에서 실행됩니다.
- 외부 웹페이지에서 가져온 정보는 AWS S3에 저장해둡니다. (다음에 가져온 정보와 비교하기 위해)
- 수동으로 실행할 수 있도록 AWS API Gateway를 통해 URL endpoint를 만들어줍니다.
- AWS Cloudwatch Event를 통해 주기적으로 자동 실행되게 합니다.

# 실행하기 전에 준비할 것

- AWS 계정
  - `aws configure` 를 실행해두어서, boto3에서 AWS Access Key Id와 Secret Access Key에 접근할 수 있도록 해 주세요.
- 알림을 받을 Slack incoming webhook url
  - https://api.slack.com/messaging/webhooks 를 참고해서 만들 수 있어요. `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX`처럼 생긴 url이에요.
  - 적당한 slack workspace가 없다면, 개인 workspace를 만드는 걸 추천드려요!
- Python 3

# 데모

Project directory에서 시작합니다.

1. `python -m pip install -r requirements.txt`

2. `config.yml` 파일을 만들어주세요. 내용은 아래와 같이 설정해 주세요. 이때 `slack_url`은 만들어둔 incoming webhook url로 채워주세요.

```yaml
lambda_name: testing
slack_url: https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
schedule_rate: 1
template:
  type: simple_json
  url: http://worldtimeapi.org/api/timezone/Asia/Seoul
  key: datetime
```

3. `python deploy.py` 를 실행한 후, `Done.` 메세지가 나올 때 까지 기다려 주세요.

4. 1분마다 한번씩 slack_url로 저번에 기록된 시간과 현재 시간을 알려주는 메세지가 올 거에요. 이 이벤트를 수동으로 실행하고 싶다면, 실행 로그 아래쪽에 `Endpoint created: https://42c7bxxxxx.execute-api.ap-northeast-2.amazonaws.com/testing` 와 같은 메세지를 확인하고, 해당 링크를 클릭해주세요.

데모 후 정리: 1분마다 한번씩 자동으로 전송되는 메세지를 끄기 위해, `config.yml` 에 있는 `schedule_rate`를 `-1` 로 수정 후, 다시 `python deploy.py` 를 실행해 주세요.

# 설정

## Resolving config.yml

Autolambda는 deploy.py 를 실행한 directory에 있는 config.yml파일을 우선적으로 설정 파일로 사용합니다.

`python deploy.py`

이를 Command line argument로 overwrite할 수도 있습니다.

`python deploy.py some/relative/directory/my_little_config.yml`

## config.yml Schema

```yaml
lambda_name: String # 만들어질 Lambda의 이름
slack_url: String # 알림을 보낼 Webhook URL
schedule_rate: Integer # (Optional) Cloudwatch Event의 주기입니다. -1로 설정한다면 Cloudwatch Event를 만들지 않습니다. 디폴트는 -1입니다.
script_file: String # (Optional) lambda_function.py 에 있는 함수를 덮어쓸 함수가 들어있는 파이썬 파일의 경로입니다.

template: # Optional
  type: String # 사용할 template의 이름. 이 이름 그대로 template폴도 내에서 import할 template을 지정합니다.
  # 그 외 template에서 필요한 variable들. 프로젝트의 template 폴더 내에서 개별 template을 확인해 보세요.
```

# OS

현재 Ubuntu에서만 테스트되었습니다.
