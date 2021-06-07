import time
from werkzeug.serving import WSGIRequestHandler
from flask import Flask, request, Response, stream_with_context, make_response
import requests
import threading

app = Flask(__name__)
SITE_NAME = 'http://10.64.45.228'
recThread = None
sem = threading.Semaphore()
buffer = []

excluded_headers = ['content-encoding', 'transfer-encoding']
# excluded_headers = ['content-encoding', 'transfer-encoding', 'content-length', 'connection']
default_headers = [('Connection','Keep-Alive'), ('Content-Type','multipart/x-mixed-replace; boundary="---osclivepreview---"'), ('X-Content-Type-Options','nosniff')]
# headers = [('Connection','Keep-Alive'),
# ('Content-Type','multipart/x-mixed-replace; boundary="---osclivepreview---"'),
# ('X-Content-Type-Options','nosniff'),
# ('Transfer-Encoding', 'Chunked')]

def recordMjpeg(response):
    # f = open('mjpegRec', "w+b")
    for line in response.iter_content(chunk_size=None):
        sem.acquire()
        # print("working")
        # f.write(line)
        buffer.append(line)
        sem.release()

def generateMjpeg():
    bytes = b''
    
    # f = open("mjpegRec", "r+b")
    # for line in f.readlines():
    while True:
        sem.acquire()
        bytes += buffer.pop(0)
        sem.release()
        a = bytes.find(b'\xff\xd8')
        b = bytes.find(b'\xff\xd9')
        if a != -1 and b != -1:
            jpg = bytes[a:b+2]
            # bytes = bytes[b+2:]
            # HERE TRUNCATE START OF FILE FOR b BYTES
            # f.close()
            
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
        print(line)
        yield "{}\n".format(time.time())
        yield line
        time.sleep(0.1)

@app.route('/')
def index():
    return 'Flask is running ' + request.environ.get('SERVER_PROTOCOL')

@app.route('/<path:path>',methods=['GET','POST','OPTIONS'])
def proxy(path):

    if request.method=='POST':
        if (request.get_json() is not None) and (request.get_json()["name"] == "camera.recordMjpeg"):
            print("recordMjpeg")
            request.get_json()["name"] = "camera.getLivePreview"
            resp = requests.post(SITE_NAME+'/'+path, stream=True, json=request.get_json())
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]

            #Call recordMjpeg thread
            recThread = threading.Thread(target=recordMjpeg, args=(resp,), daemon=True)
            recThread.start()

            response = make_response()

        elif (request.get_json() is not None) and (request.get_json()["name"] == "camera.getJpeg"):
            # print("getJpeg")
            
            response = Response(
                generateMjpeg(),
                200,
                default_headers
            )
        
        elif (request.get_json() is not None) and (request.get_json()["name"] == "camera.getLivePreview"):
            print("livePreview")
            resp = requests.post(SITE_NAME+'/'+path, stream=True, json=request.get_json())
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
            
            response = Response(
                stream_with_context(resp.iter_content(chunk_size=None)),
                resp.status_code,
                headers
            )
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
