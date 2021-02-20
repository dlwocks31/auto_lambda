from pyquery import PyQuery as pq


def fetch_data(**kwargs):
    url = kwargs['url']
    selector = kwargs['selector']
    doc = pq(url)
    return doc(selector).text()
