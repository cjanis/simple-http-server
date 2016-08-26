import sys
import logging
import json
import time

from flask import Flask, render_template, make_response, request, Response, current_app

LOGGER_FILE_NAME = 'access.log'
JSON_LOGGER_FILE_NAME = 'access.log.json'

app = Flask(__name__)

class LogRequest(object):
    """descprption goes here
    TODO: make this as a Flask object
    """

    NGINX_ADDED_HEADERS = [
                            'x-remote-addr',
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

    def __init__(self, request_object, nginx=False):
        """constructor"""
        # it seems it is actually better to make an extension to flask.Request
        # class and use it instead of doing this
        self.request = request_object
        self._delete_extra_headers()
        self.request.headers_json = self.headers_to_json()
        self.nginx_extra_data = self.extract_nginx_headers_data()

    def extract_nginx_headers_data(self):
        """method to extract data from nginx added headers
        """
        data = {}
        environ_copy = self.request.environ.copy()

        # if header name in NGINX_ADDED_HEADERS extract data 
        # and remove this header
        for env_key, env_val  in environ_copy.iteritems():
            # HTTP_X_SERVER_ADDR -> x-server-addr
            nginx_header = env_key.lower().replace('_','-')[5:]
            if nginx_header in self.NGINX_ADDED_HEADERS:
                # data.append({nginx_header: env_val})
                data[nginx_header] = env_val
                self.request.environ.pop(env_key)

        for header in self.NGINX_ADDED_HEADERS:
            if header not in data:
                data[header] = '0'
        return data


    def headers_to_json(self):
        """Converts list of headers to list of header name: value pairs"""
        return {header[0]: header[1] for header in request.headers}


    def _delete_extra_headers(self):
        """for a some reason Flask' request.headers always contains few headers
        # need to check if reqest.headers 'Content-type' ot 'Content-length'
        # values are empty, then do not include them into list of headers
        # It will also remove these two headers in case client send them, but
        # value was empty.
        # Need to fix/file Flask issue to fix this and also preserve headers 
        # order
        this method just clean up request object by removing thes extra headers
        """
        extra_headers = [
                        'content-type',
                        'content-length'
                        ]

        environ_copy = self.request.environ.copy()
        for r_header, r_value in environ_copy.iteritems():
            if ((r_header.lower().replace('_','-') in extra_headers and r_value == '') or (r_header.lower().replace('_','-') in extra_headers and r_value != '')):
                self.request.environ.pop(r_header)
        return True

    def headers_to_string(self):
        """ returns request headers as string of header_name:header_value
        using | as a delimiter bw headers
        """
        headers_str = ''
        always_added_headers = [
                                'Content-type',
                                'Content-length'
                               ]
        for header in self.request.headers:
            # for a some reason Flask' request.headers always contains few headers
            # need to check if reqest.headers 'Content-type' ot 'Contetn-length'
            # values are empty, then do not include them into list of headers
            # It will also remove these two headers in case client send them, but
            # value was empty.
            # Need to fix/file Flask issue to fix this and also preserve headers 
            # order
            if header[0] not in always_added_headers and header[1] != '': 
                headers_str = headers_str + '{}:{}|'.format(header[0], header[1])

        return headers_str

    def headers_to_json_string(self):
        """returns headers json formatted string
        """ 
        return json.dumps(self.headers_to_json())

    def quesry_to_json_string(self):
        """returns query json formatted string
        """
        query = {}
        for item in self.request.args.lists():
            if len(item[1]) > 1:
                for value in item[1]:
                    query[item[0]] = value
            else:
                query[item[0]] = item[1][0]
        return json.dumps(query)


@app.before_request
def log_entry():

    # TODO: add config option
    proceed_request = LogRequest(request, nginx=True)
    headers = proceed_request.headers_to_string()
    extra_data = proceed_request.nginx_extra_data
    # TODO: proper IPv6 handling
    # TODO: figure out why 
    context = {
        "remote_ip": extra_data["x-remote-addr"],
        "remote_port": extra_data["x-remote-port"],
        "http_version": extra_data["x-server-protocol"],
        "server_port": extra_data["x-server-port"],
        "secure": extra_data["x-is-secure"],
        "target_host": extra_data['x-host'],
        "tcp_rtt": extra_data['x-tcp-rtt'],
        "tcp_rttvar": extra_data['x-tcp-rttvar'],
        "tcp_snd_cwd": extra_data['x-tcp-snd-cwd'],
        "tcp_rcv_space": extra_data['x-tcp-rcv-space'],
        "method": request.method,
        "path": request.path,
        "query": proceed_request.quesry_to_json_string(),
        "headers": proceed_request.headers_to_json_string(),
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
                     '"tcp_info": { '\
                        '"tcp_rtt": "%(tcp_rtt)s", '\
                        '"tcp_rttvar": "%(tcp_rttvar)s", '\
                        '"tcp_snd_cwd": "%(tcp_snd_cwd)s", '\
                        '"tcp_rcv_space": "%(tcp_rcv_space)s"'\
                         '}'\
                    '}', context)

@app.route('/', defaults={'path': ''}, methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
@app.route('/<path:path>', methods=['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def hello_world(path):
    return 'Ok\n'


if __name__ == "__main__":

    # TODO: make this a configurable
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    print('Starting test server on port {0}'.format(port))

    json_file_handler = logging.FileHandler(JSON_LOGGER_FILE_NAME)
    # %(created)f <- time.time() to convert to ms int(time.time()*1000)
    json_formatter = logging.Formatter('{"timestamp": "%(created)f", "time": "%(asctime)s", "loglevel": "%(levelname)s", "request_data": %(message)s}')
    # set formatter to use gmt format
    json_formatter.converter = time.gmtime
    json_file_handler.setFormatter(json_formatter)

    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(json_file_handler)

    # TODO: make this configurable
    # app.run('0.0.0.0', port=port)
    app.run(port=port)