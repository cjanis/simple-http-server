import sys
import logging
import json
import time

from flask import Flask, render_template, make_response, request, Response, current_app

LOGGER_FILE_NAME = 'access.log'
JSON_LOGGER_FILE_NAME = 'access.log.json'

app = Flask(__name__)

class LogRequest(object):
    """descprption goes here"""

    def __init__(self, request_object):
        """constructor"""
        # it seems it is actually better to make an extension to flask.Request
        # class and use it instead of doing this
        self.request = request_object
        self._deleate_extra_headers()
        self.request.headers_json = self.headers_to_json()

    def headers_to_json(self):
        """Converts list of headers to list of header name: value pairs"""
        return [{'name': header[0], 'value': header[1]} for 
                header in request.headers]


    def _deleate_extra_headers(self):
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
        clean_headers = [header for header in self.request.headers if ((header[0].lower() not in extra_headers and header[1] != '') 
                            or (header[0].lower() not in extra_headers and header[1] == ''))]
        self.request.headers = clean_headers
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
        query = []
        for item in self.request.args.lists():
            if len(item[1]) > 1:
                for value in item[1]:
                    query.append({'name': item[0], 'value': value})
            else:
                query.append({'name': item[0], 'value': item[1][0]})
        return json.dumps(query)


@app.before_request
def log_entry():

    print(request.headers)
    proceed_request = LogRequest(request)

    headers = proceed_request.headers_to_string()
    print(request.url)

    # TODO: proper IPv6 handling
    # TODO: figure out why 
    context = {
        'remote_ip': request.remote_addr,
        'method': request.method,
        'path': request.path,
        'query': proceed_request.quesry_to_json_string(),
        'headers': proceed_request.headers_to_json_string(),
        'port': request.url.split('/')[2].split(":")[1]
    }

    app.logger.info('{"remote_ip": "%(remote_ip)s", "method": "%(method)s", '\
                     '"path": "%(path)s", "query": %(query)s, '\
                     '"headers": %(headers)s , "port": "%(port)s"'\
                    '}', context)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def hello_world(path):
    return 'Ok\n'


if __name__ == "__main__":

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

    app.run('0.0.0.0', port=port)
    # app.run(port=port)