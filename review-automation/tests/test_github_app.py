import os
import json
import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import github_app as app
import controller as c


class AppSecret(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows DPAPI only")
    def test_dpapi_round_trip(self):
        value = b"nonsecret-fixture-for-roundtrip"
        encrypted = app.protect(value)
        self.assertNotIn(value, encrypted)
        self.assertEqual(app.protect(encrypted, decrypt=True), value)

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI only")
    def test_file_contains_only_encrypted_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "app.dpapi"
            app.save_secret(path, {"pem": "not-a-real-secret", "id": 1})
            self.assertNotIn(b"not-a-real-secret", path.read_bytes())
            self.assertEqual(app.load_secret(path)["id"], 1)

    @unittest.skipUnless(shutil.which("node"), "Node.js required")
    def test_real_rs256_signature_and_repository_scoped_token(self):
        node = shutil.which("node")
        generated = c.run_process([node, "-e", "const c=require('crypto'); const k=c.generateKeyPairSync('rsa',{modulusLength:2048,publicKeyEncoding:{type:'spki',format:'pem'},privateKeyEncoding:{type:'pkcs8',format:'pem'}}); console.log(JSON.stringify(k));"], timeout=15)
        keys = json.loads(generated.stdout)
        captured = {}
        class Fake:
            def __init__(self, repo, token):
                self.token = token
                if token != "fixture-installation-token":
                    captured["jwt"] = token
            def request(self, path, method="GET", body=None):
                if path == "/app":
                    return {"id": 17, "slug": "fixture-reviewer"}
                if path.endswith("/installation"):
                    return {"id": 29}
                captured["scope"] = body
                return {"token": "fixture-installation-token"}
        with patch("github_app.load_secret", return_value={"id": 17, "client_id": "fixture", "installation_id": 29, "pem": keys["privateKey"]}), patch("controller.GitHub", Fake):
            client = app.app_client("unused", "owner/project")
        self.assertEqual(client.actor, "fixture-reviewer[bot]")
        self.assertEqual(captured["scope"]["repositories"], ["project"])
        self.assertEqual(captured["scope"]["permissions"]["contents"], "read")
        verification = c.run_process([node, "-e", "const c=require('crypto');let x='';process.stdin.on('data',v=>x+=v);process.stdin.on('end',()=>{const v=JSON.parse(x),p=v.jwt.split('.');const claims=JSON.parse(Buffer.from(p[1],'base64url'));process.exit(c.verify('RSA-SHA256',Buffer.from(p[0]+'.'+p[1]),v.key,Buffer.from(p[2],'base64url'))&&claims.iss==='fixture'&&claims.exp-claims.iat<=600?0:1);});"],
            input=json.dumps({"jwt": captured["jwt"], "key": keys["publicKey"]}), timeout=15)
        self.assertEqual(verification.returncode, 0)


if __name__ == "__main__":
    unittest.main()
