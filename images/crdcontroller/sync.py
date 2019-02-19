from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import json
import os

def make_desired(name, spec):
   configname =  "{}-config".format(name)
   claimname  = "mylocal-pvc"
   children = [
       {
         "apiVersion": "v1",
         "data": {
            "workflow.yml": json.dumps(spec)
         },
         "kind": "ConfigMap",
         "metadata": {
            "name": configname
         }
      }
      ,
      {
         "apiVersion": "batch/v1",
         "kind": "Job",
         "metadata": {
            "name": "{}-wflow-job".format(name)
         },
         "spec": {
            "backoffLimit": 0,
            "template": {
               "spec": {
                  "containers": [
                     {
                        "command": [
                           "yadage-run","-f","/etc/config/workflow.yml"
                        ],
                        "image": os.environ['YADKUBE_IMAGE'],
                        "imagePullPolicy":  os.environ['YADKUBE_IMAGE_POLICY'],
                        "name": "runner",
                        "volumeMounts": [
                           {
                              "mountPath": "/data",
                              "name": "data"
                           },
                           {
                              "mountPath": "/etc/config",
                              "name": "config-volume"
                           }
                        ],
                        "workingDir": "/data"
                     }
                  ],
                  "restartPolicy": "Never",
                  "volumes": [
                     {
                        "name": "data",
                        "persistentVolumeClaim": {
                           "claimName": claimname
                        }
                     },
                     {
                        "configMap": {
                           "name": configname
                        },
                        "name": "config-volume"
                     }
                  ]
               }
            }
         }
      }   
   ]
   return children

class Controller(BaseHTTPRequestHandler):
   def sync(self, parent, children):
      print('syncing!',children)
      # Compute status based on observed state.
      desired_status = {
         "cmap": len(children["ConfigMap.v1"]),
         "jobs": len(children["Job.batch/v1"])
      }

      # Generate the desired child object(s).
      spec  = parent.get("spec", {})
      name = parent["metadata"]["name"]
    
      children = make_desired(name, spec)

      print('ok children',children)
    
      return {"status": desired_status, "children": children}

   def do_POST(self):
      # Serve the sync() function as a JSON webhook.
      observed = json.loads(self.rfile.read(int(self.headers.getheader("content-length"))))
      desired = self.sync(observed["parent"], observed["children"])

      self.send_response(200)
      self.send_header("Content-type", "application/json")
      self.end_headers()
      self.wfile.write(json.dumps(desired))

HTTPServer(("", 80), Controller).serve_forever()
