import time
from werkzeug.serving import WSGIRequestHandler
from flask import Flask, request, Response, stream_with_context, make_response
import requests
import threading
import collections
import signal
import json

def handler(signum, frame):
	print("closing")
	exit(0)

signal.signal(signal.SIGINT, handler)

app = Flask(__name__)
SITE_NAME = 'http://10.64.45.228'
EXECUTE_PATH = '/osc/commands/execute'
LIVE_CMD = '{"name": "camera.getLivePreview"}'
recThread = None
sem = threading.Semaphore()
buffer = collections.deque([], maxlen=2)

excluded_headers = ['content-encoding', 'transfer-encoding']
# excluded_headers = ['content-encoding', 'transfer-encoding', 'content-length', 'connection']
default_headers = [('Connection','Keep-Alive'), ('X-Content-Type-Options','nosniff')]
# headers = [('Connection','Keep-Alive'),
# ('Content-Type','multipart/x-mixed-replace; boundary="---osclivepreview---"'),
# ('X-Content-Type-Options','nosniff'),
# ('Transfer-Encoding', 'Chunked')]

def recordMjpeg(response):
    bytes = b''
    a = -1
    b = -1

    for line in response.iter_content(chunk_size=None):
        bytes += line
        if a == -1:
            a = bytes.find(b'\xff\xd8')
            
        b = bytes.find(b'\xff\xd9')
        if a != -1 and b != -1:
            jpg = bytes[a:b+2]
            bytes = bytes[b+2:]
            a = -1
            b = -1
            
            sem.acquire()
            # print("from thread")
            buffer.append(jpg)
            # print(len(buffer))
            sem.release()

def generateMjpeg():
    jpg = None
    while True:
        sem.acquire()
        if len(buffer) > 0:
            jpg = buffer.popleft()
        sem.release()
        if jpg is not None:
            return jpg
        
def readContentLength(response):
    start = time.time()
    # for line in response.iter_lines(chunk_size=8192):
    for line in response.iter_content(chunk_size=24):
        try:
            # print(line)
            data = line.decode('ascii')
            
            if(data.startswith("Content-Length")):
                length = data.split(": ")
                print("Content-Length ", length[1])
                print((time.time() - start))
                start = time.time()
        except (UnicodeDecodeError, AttributeError):
            pass
        # print(line)
        yield line

@app.route('/')
def index():
    return 'Flask is running ' + request.environ.get('SERVER_PROTOCOL')

@app.route('/get_stream', methods=['GET'])
def stream():
    print("get stream")
    resp = requests.post(SITE_NAME+EXECUTE_PATH, stream=True, json=json.loads(LIVE_CMD))
    headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
    
    response = Response(
        stream_with_context(resp.iter_content(chunk_size=None)),
        resp.status_code,
        headers
    )

    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    # response.headers.add('Cross-Origin-Opener-Policy', "same-origin")
    # response.headers.add('Cross-Origin-Embedder-Policy', "require-corp")
    return response

@app.route('/<path:path>',methods=['GET','POST','OPTIONS'])
def proxy(path):
    global recThread

    if request.method=='POST':
        if (request.get_json() is not None) and (request.get_json()["name"] == "camera.recordMjpeg"):

            #Call recordMjpeg thread
            if recThread is None:
                print("Start recording Mjpeg")
                request.get_json()["name"] = "camera.getLivePreview"
                resp = requests.post(SITE_NAME+'/'+path, stream=True, json=request.get_json())
                # headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
                recThread = threading.Thread(target=recordMjpeg, args=(resp,), daemon=True)
                recThread.start()
            else:
                print("Reset recording Mjpeg")
                sem.acquire()
                buffer.clear()
                print("deque cleared")
                sem.release()

            response = make_response()

        elif (request.get_json() is not None) and (request.get_json()["name"] == "camera.getJpeg"):
            # print("getJpeg")
            
            response = Response(
                generateMjpeg(),
                200,
                default_headers
            )
        
        elif (request.get_json() is not None) and (request.get_json()["name"] == "camera.getLivePreview"):
            print("livePreview stream")
            resp = requests.post(SITE_NAME+'/'+path, stream=True, json=request.get_json())
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
            
            response = Response(
                stream_with_context(resp.iter_content(chunk_size=None)),
                resp.status_code,
                headers
            )
            # response = Response(
            #     readContentLength(resp),
            #     resp.status_code,
            #     headers
            # )
        # REGULAR POST
        else:
            if request.get_json() is not None:
                print(request.get_json()["parameters"]["options"]["previewFormat"])

            resp = requests.post(SITE_NAME+'/'+path,json=request.get_json())

            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
            # headers = [(name, value) for (name, value) in resp.raw.headers.items()]
            response = Response(resp.content, resp.status_code, headers)
        
    elif request.method=='GET':
        # print(SITE_NAME+'/'+path)
        resp = requests.get(SITE_NAME+'/'+path)
        
        headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        response = Response(resp.content, resp.status_code, headers)
        
    elif request.method=='OPTIONS':
        # resp = requests.options(SITE_NAME+'/'+path)
        # headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        # response = Response(resp.content, resp.status_code, headers)
        response = make_response()
    
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add('Access-Control-Allow-Headers', "*")
    response.headers.add('Access-Control-Allow-Methods', "*")
    # response.headers.add('Cross-Origin-Opener-Policy', "same-origin")
    # response.headers.add('Cross-Origin-Embedder-Policy', "require-corp")
    return response

if __name__ == '__main__':
    WSGIRequestHandler.protocol_version = "HTTP/1.1"

    context = ('local.crt', 'local.key')#certificate and key files
    # context = ('cert.pem', 'key.pem')#certificate and key files
    # app.config['MAX_CONTENT_LENGTH'] = 9999999
    app.run(host="0.0.0.0", debug=True, ssl_context=context)
    # app.run(host="0.0.0.0", debug=True)
