import sys
import json
import time
import argparse
import os
import logging
from logging.handlers import TimedRotatingFileHandler

from flask import Flask, render_template, make_response, request, Response, current_app
from werkzeug.datastructures import Headers, MultiDict


class HeadersParser(object):
    """Parse request headers
    """

    NGINX_ADDED_HEADERS = ['x-remote-addr',
                           'x-remote-port',
                           'x-server-addr',
                           'x-host',
                           'x-scheme',
                           'x-is-secure',
                           'x-server-protocol',
                           'x-server-port',
                           'x-tcp-rtt',
                           'x-tcp-rttvar',
                           'x-tcp-snd-cwd',
                           'x-tcp-rcv-space',
                          ]

    def __init__(self, headers_obj):
        """
        headers_obj: request.headers object
        """
        self.headers = Headers(headers_obj)

    def remove_extra_headers(self):
        extra_headers = ['content-type',
                         'content-length'
                        ]
        for header in self.headers.items():
            h_name = header[0]
            h_value = header[1]
            if (h_name.lower() in extra_headers and h_value == '')\
                or (h_name.lower in extra_headers and h_value != ''):
                del self.headers[h_name]
        return True

    def extract_nginx_headers_data(self, remove_data=True):
        """method to extract data from nginx added headers
        """
        data = {}

        # if header name in NGINX_ADDED_HEADERS extract data

        for header in self.headers:
            h_name = header[0].lower()
            h_value = header[1]
            if h_name in self.NGINX_ADDED_HEADERS:
                data[h_name] = h_value

        if remove_data:
            self.remove_nginx_headers()

        # if header is missing set it's value to 0
        for header in self.NGINX_ADDED_HEADERS:
            if header not in data:
                data[header] = '0'

        return data

    def remove_nginx_headers(self):
        """ method to delete all Nginx added headers from request headers
        """
        for header in self.headers.items():
            h_name = header[0]
            if h_name.lower() in self.NGINX_ADDED_HEADERS:
                del self.headers[h_name]

        return True

    def headers_to_json(self):
        """Converts list of headers to list of header name: value pairs"""
        return {header[0]: header[1] for header in self.headers}


class MultiDictParser(object):
    """
    werkzeug.datastructures.MultiDict to dict
    """

    def __init__(self, multidict):
        self.multidict = multidict

    def to_json(self):
        """
        converts MultiDict to regular json dict. It uses the samem method as
        MultiDict.to_dict(flat=Flase), but returns structure like
        {'name': 'v1', 'name': 'v2'} instead of {'name': ['v1', v2]}
        """
        res = {}
        for item in self.multidict.lists():
            if len(item[1]) > 1:
                val_list = []
                for value in item[1]:
                    val_list.append(value)
                res[item[0]] = val_list
            else:
                res[item[0]] = item[1][0]
        return res


class BodyParser(object):

    def __init__(self, request_obj):
        self.request = request_obj

    def get_body(self):
        """
        extracts and returns request body. returns body as string
        First it checks for known content type, if content type
        application/x-www-form-urlencoded it converts it to json using MultiDictParser
        application/*+json returns json
        all other types just return request.data
        """
        body = json.dumps({})
        if ('content-length' in self.request.headers) and (self.request.headers['content-length'] != ''):
            if self.request.headers.get('content-type') == 'application/x-www-form-urlencoded':
                body = json.dumps(MultiDictParser(self.request.form).to_json())
            elif self.request.is_json:
                body = json.dumps(self.request.get_json())
            else:
                body = json.dumps(self.request.data)
        return body

LOGGER_FILE_NAME = 'access.log.json'
MAX_LOG_SIZE = 20971520
NUMBER_OF_LOG_FILES = 100
ROTATION_INTERVAL = 'D'
ROTATION_DAYS = 30


parser = argparse.ArgumentParser()
parser.add_argument("--log-directory", dest='log_directory',
                    help='Input json file with shodan data',
                    default=(os.path.dirname(os.path.realpath(__file__))))
parser.add_argument("--app-port", dest='port',
                    help='Port flask app will listen on',
                    default=8000)

args = parser.parse_args()
log_file = os.path.join(os.path.abspath((os.path.expanduser(args.log_directory))), LOGGER_FILE_NAME)
port = args.port
app = Flask(__name__)

# json_file_handler = RotatingFileHandler(log_file, maxBytes=MAX_LOG_SIZE,
#                                         backupCount=NUMBER_OF_LOG_FILES)
json_file_handler = TimedRotatingFileHandler(log_file, when=ROTATION_INTERVAL,
                                             backupCount=ROTATION_DAYS)
json_formatter = logging.Formatter('{"timestamp": "%(created)f", "time": "%(asctime)s", "loglevel": "%(levelname)s", "request_data": %(message)s}')
# set formatter to use gmt format
json_formatter.converter = time.gmtime
json_file_handler.setFormatter(json_formatter)
app.logger.setLevel(logging.INFO)
app.logger.addHandler(json_file_handler)


@app.route('/', defaults={'path': ''}, methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def hello_world(path):
    return 'Ok\n'


@app.before_request
def log_entry():

    parsed_headers = HeadersParser(request.headers)
    # remove Nginx added headers
    parsed_headers.remove_extra_headers()
    nginx_data = parsed_headers.extract_nginx_headers_data()
    client_headers = json.dumps(parsed_headers.headers_to_json())
    query = json.dumps(MultiDictParser(request.args).to_json())
    body = BodyParser(request).get_body()

    context = {
        "remote_ip": nginx_data["x-remote-addr"],
        "remote_port": nginx_data["x-remote-port"],
        "http_version": nginx_data["x-server-protocol"],
        "server_port": nginx_data["x-server-port"],
        "secure": nginx_data["x-is-secure"],
        "target_host": nginx_data['x-host'],
        "tcp_rtt": nginx_data['x-tcp-rtt'],
        "tcp_rttvar": nginx_data['x-tcp-rttvar'],
        "tcp_snd_cwd": nginx_data['x-tcp-snd-cwd'],
        "tcp_rcv_space": nginx_data['x-tcp-rcv-space'],
        "method": request.method,
        "path": request.path,
        "query": query,
        "headers": client_headers,
        "body": body
    }

    app.logger.info('{'\
                     '"remote_ip": "%(remote_ip)s", '\
                     '"remote_port": "%(remote_port)s", '\
                     '"server_port": "%(server_port)s", '\
                     '"target_host": "%(target_host)s", '\
                     '"http_version": "%(http_version)s", '\
                     '"secure": "%(secure)s", '\
                     '"method": "%(method)s", '\
                     '"path": "%(path)s", '\
                     '"query": %(query)s, '\
                     '"headers": %(headers)s, '\
                     '"body": %(body)s, '\
                     '"tcp_info": { '\
                        '"tcp_rtt": "%(tcp_rtt)s", '\
                        '"tcp_rttvar": "%(tcp_rttvar)s", '\
                        '"tcp_snd_cwd": "%(tcp_snd_cwd)s", '\
                        '"tcp_rcv_space": "%(tcp_rcv_space)s"'\
                         '}'\
                    '}', context)


if __name__ == "__main__":
    app.run(port=port)
