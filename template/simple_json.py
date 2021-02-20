from requests import get


def fetch_data(**kwargs):
    url = kwargs['url']
    key = kwargs['key']
    data = get(url).json()
    key_arr = key.split('.')
    for k in key_arr:
        data = data[k]
    return data
