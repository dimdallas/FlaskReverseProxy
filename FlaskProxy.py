from flask import Flask, request, Response, stream_with_context, make_response
import requests
app = Flask(__name__)
SITE_NAME = 'http://10.64.45.228'

@app.route('/')
def index():
    return 'Flask is running!'

@app.route('/<path:path>',methods=['GET','POST','OPTIONS'])
def proxy(path):
    # global SITE_NAME
    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']

    if request.method=='GET':
        # print(SITE_NAME+'/'+path)
        resp = requests.get(SITE_NAME+'/'+path)
        
        headers = [(name, value) for (name, value) in     resp.raw.headers.items() if name.lower() not in excluded_headers]
        response = Response(resp.content, resp.status_code, headers)
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        return response
    elif request.method=='POST':
        # print(request.get_json())
        if (request.get_json() is not None) and (request.get_json()["name"] == "camera.getLivePreview"):
            print("live")
            resp = requests.post(SITE_NAME+'/'+path, stream=True, json=request.get_json())
            # headers = [('Connection','Keep-Alive'), ('Content-Type','multipart/x-mixed-replace; boundary="---osclivepreview---"'), ('X-Content-Type-Options','nosniff'), ('Transfer-Encoding', 'Chunked')]
            headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
            # return Response(
            #     stream_with_context(req.iter_content(chunk_size=8192)),
            #     content_type = resp.headers['content-type'],
            #     headers=dict(resp.headers).update({
            #         # Per the terms of the AGPL, these following headers MAY NOT
            #         # be removed! They MUST be returned to the client.
            #         'X-Powered-By': 'github.com/jantman/python-amcrest-noauth-proxy',
            #         'X-License': 'GNU Affero General Public License v3 or later'
            #     })
            # )
            response = Response(
                stream_with_context(resp.iter_content(chunk_size=8192)),
                resp.status_code,
                headers
            )
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add('Access-Control-Allow-Headers', "*")
            response.headers.add('Access-Control-Allow-Methods', "*")
            return response

        if request.get_json() is not None:
            print(request.get_json())

        resp = requests.post(SITE_NAME+'/'+path,json=request.get_json())

        headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        response = Response(resp.content, resp.status_code, headers)
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', "*")
        response.headers.add('Access-Control-Allow-Methods', "*")
        # print(response)
        return response
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
    # context = ('local.crt', 'local.key')#certificate and key files
    context = ('cert.pem', 'key.pem')#certificate and key files
    # app.run(host="0.0.0.0", debug=True)
    app.run(host="0.0.0.0", debug=True, ssl_context='adhoc')
    # app.run(host="0.0.0.0", debug=True, ssl_context=context)