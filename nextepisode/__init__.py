__author__ = "Gabriel Melillo<gabriel@melillo.me>"
__version__ = "0.5.7"

import mechanize
from uuid import uuid3, NAMESPACE_OID
from urllib import urlencode
from regexp import regexp_search, Expression
from httplib2 import Http
from httplib import BadStatusLine
from bs4 import BeautifulSoup
from time import time2str, get_offset_time, str2time
from socket import error as socket_error
from cache import TVRageCache


class List(object):
    list = []

    def __init__(self, default=[]):
        self.list = default

    def __getitem__(self, item):
        return self.list[item]

    def __iter__(self):
        for item in self.list:
            yield item

    def __len__(self):
        return len(self.list)

    def __setitem__(self, key, value):
        self.list[key] = value

    def __repr__(self):
        return "<{} List of {} item>".format(self.__class__.__name__, self.__len__())

    def __str__(self):
        return self.__repr__()

    def append(self, value):
        for item in self.list:
            if item == value:
                return False
        self.list.append(value)
        return True


class NextEpisode(List):
    rooturl = "http://next-episode.net"

    def __init__(self, username, password, **kwargs):
        super(List, self).__init__()
        self.browser = mechanize.Browser()
        self.browser.addheaders = [('User-agent', 'Firefox')]
        self.add_show = self.append
        self.today_list = []

        self._cache_dir = '/tmp/.necd'
        self._logghedin = False
        self._username = username
        self._password = password
        self._offset = kwargs.get('offset', 0)

        self._cache = TVRageCache(cachefile=kwargs.get('cachefile', TVRageCache.DEFAULT_CACHE_FILE))

        if kwargs.get('autologin', True):
            self.do_login(
                username=username,
                password=password
            )

        if kwargs.get('autoupdate', True):
            self.update_list()

    def __repr__(self):
        return "<{} {}@next-episode.net WL: {} Shows>".format(self.__class__.__name__, self._username, self.__len__())

    def do_login(self, username, password):
        self.browser.open(self.rooturl)
        self.browser.select_form(name="login")
        self.browser.form['username'] = username
        self.browser.form['password'] = password
        self.browser.submit()
        self._logghedin = True

    def update_list(self):
        if not self._logghedin:
            self.do_login(self._username, self._password)

        html = self.browser.open(self.rooturl+'/user/'+self._username).read()
        soup = BeautifulSoup(html)
        divs = soup.findAll('div',
                            attrs={
                                'class': 'item'
                            })
        self.list = []
        for div in divs:
            spans = div.findAll('span',attrs={'class':'headlinehref'})
            for span in spans:
		link = span.find("a")
                if link.contents[0] == "V":
                    link.contents[0] = "V (2009)"
                try:
                    self.append({
                        'Name': [link.get_text()],
                        'index': uuid3(NAMESPACE_OID, link.get('href').encode('utf8', 'ignore')).__str__(),
                        'URL': self.rooturl+link.get('href').encode('utf8', 'ignore')
                    })
                except UnicodeDecodeError:
                    self.append({
                        'Name': [link.contents[0]],
                        'index': 'N/A',
                        'URL': self.rooturl+link.get('href').encode('utf8', 'ignore')
                    })

    def _regexp_tvrage(self, content):
        return {
            'Show ID': regexp_search(Expression.SHOW_ID, content),
            'Show Name': regexp_search(Expression.SHOW_NAME, content),
            'URL': regexp_search(Expression.URL, content),
            'Premiered': regexp_search(Expression.PREMIERED, content),
            'Country': regexp_search(Expression.COUNTRY, content),
            'Status': regexp_search(Expression.STATUS, content),
            'Classification': regexp_search(Expression.CLASSIFICATION, content),
            'Genres': regexp_search(Expression.GENRES, content),
            'Network': regexp_search(Expression.NETWORK, content),
            'Airtime': regexp_search(Expression.AIRTIME, content),
            'Latest Episode': {
                'Number': regexp_search(Expression.LEPISODE, content, number=1),
                'Title': regexp_search(Expression.LEPISODE, content, number=2),
                'Air Date': get_offset_time(
                    regexp_search(Expression.LEPISODE, content, number=3),
                    offset=self._offset
                )
            },
            'Next Episode': {
                'Number': regexp_search(Expression.NEPISODE, content, number=1),
                'Title': regexp_search(Expression.NEPISODE, content, number=2),
                'Air Date': get_offset_time(
                    regexp_search(Expression.NEPISODE, content, number=3),
                    offset=self._offset
                )
            }
        }

    def attach_tvrage_info(self):
        for idx, show in enumerate(self.list):
            h = Http(self._cache_dir)
            url = "http://services.tvrage.com/tools/quickinfo.php?{}".format(
                urlencode({
                    'show': show['Name'][0].__str__(),
                    'exact': 1
                })
            )
            _today = time2str()

            self.list[idx]['TV Rage'] = self._cache.get_cache(self.list[idx]['index'])
            if self.list[idx]['TV Rage'] is None:
                try:
                    resp, content = h.request(url)
                except socket_error:
                    resp, content = ("", "")
                except BadStatusLine:
                    resp, content = ("", "")

                self.list[idx]['TV Rage'] = self._regexp_tvrage(content)
                if self.list[idx]['TV Rage']['Next Episode']['Air Date'] == 'N/A':
                    _expire = str2time(get_offset_time(time2str(), offset=7))
                else:
                    _expire = str2time(self.list[idx]['TV Rage']['Next Episode']['Air Date'])

                self._cache.write_cache(
                    self.list[idx]['index'],
                    self.list[idx]['TV Rage'],
                    _expire
                )

            if _today == self.list[idx]['TV Rage']['Next Episode']['Air Date']:
                self.today_list.append(self.list[idx])
            if _today == self.list[idx]['TV Rage']['Latest Episode']['Air Date']:
                self.today_list.append(self.list[idx])
