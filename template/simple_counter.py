import requests


def fetch_data(**kwargs):
    url = kwargs['url']
    keyword = kwargs['keyword']
    txt = requests.get(url, headers={
                       'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.66 Safari/537.36'}).text
    return txt.count(keyword)
