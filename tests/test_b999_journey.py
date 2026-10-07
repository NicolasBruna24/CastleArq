# B9.99 journey test: admit -> describe -> bind -> acquire(resolve) -> evaluate -> execute/chat wiring.
import os, tempfile, unittest
from unittest import mock
from castlearq import admitted_models as am
from castlearq.admitted_commands import admit_command, bind_command, describe_command, refresh_command, reconcile_command
from castlearq.identity_admission import lookup as admit_lookup
from castlearq.acquisition_resolution import resolve_binding, resolve_acquisition_locator
from castlearq.model_identity import resolve_admitted_model_id
from castlearq.model_store import ModelStore
from castlearq.models import ArtifactSpec
from castlearq.resolver import ModelArtifactResolver
import io
SRC="huggingface"; REPO="someowner/journey-b9999"; REV="abc123"
class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        for k,v in [("CASTLEARQ_ADMITTED_MODELS_ROOT",self.tmp.name+"/am"),("CASTLEARQ_IDENTITY_ADMISSION_ROOT",self.tmp.name+"/id"),("CASTLEARQ_ACQUISITION_BINDINGS_ROOT",self.tmp.name+"/bn")]:
            os.environ[k]=v
        self.mid=resolve_admitted_model_id(SRC,REPO)
    def tearDown(self):
        for k in ("CASTLEARQ_ADMITTED_MODELS_ROOT","CASTLEARQ_IDENTITY_ADMISSION_ROOT","CASTLEARQ_ACQUISITION_BINDINGS_ROOT"):
            os.environ.pop(k,None)
        self.tmp.cleanup()
    def test_full_explicit_journey(self):
        out=io.StringIO();err=io.StringIO()
        self.assertEqual(admit_command(SRC,REPO,out=out,err=err),0)
        self.assertEqual(admit_lookup(SRC,REPO),self.mid)
        # describe via boundary
        self.assertEqual(describe_command(self.mid,SRC,REPO,filename="m.gguf",quantization="Q4_K_M",revision=REV,architecture="llama",fmt="GGUF",out=out,err=err),0)
        rec=am.resolve(self.mid)
        self.assertIsNotNone(rec)
        # bind via boundary
        self.assertEqual(bind_command(self.mid,SRC,REPO,out=out,err=err),0)
        self.assertEqual(resolve_binding(self.mid),(SRC,REPO))
        self.assertEqual(resolve_acquisition_locator(self.mid),(SRC,REPO))
        # simulate acquired artifact in ModelStore
        store=ModelStore(__import__("pathlib").Path(self.tmp.name)/"store")
        spec=ArtifactSpec(model_id=self.mid,source=SRC,repository=REPO,filename="m.gguf",format="GGUF",quantization="Q4_K_M",revision=REV)
        store.save_manifest(spec)
        with open(store._artifact_directory(spec)/"m.gguf","wb") as f:
            f.write(b"GGUF-fake")
        r=ModelArtifactResolver(model_store=store).resolve(self.mid,filename="m.gguf")
        self.assertEqual(r.model.model_id,self.mid)
        self.assertEqual(r.artifact.filename,"m.gguf")
        # no implicit refresh during resolution
        self.assertIsNone(am.resolve(self.mid).pending_declaration)
        # explicit refresh + reconcile
        self.assertEqual(refresh_command(self.mid,architecture="llama",fmt="GGUF",out=out,err=err),0)
        self.assertIsNotNone(am.resolve(self.mid).pending_declaration)
        self.assertEqual(reconcile_command(self.mid,{"architecture":"accept_pending"},basis="human-test",out=out,err=err),0)
        self.assertIsNone(am.resolve(self.mid).pending_declaration)
        # conflict blocks
        am.record_observation(self.mid,"gguf_architecture","other-arch",observation_context="t")
        with self.assertRaises(Exception):
            ModelArtifactResolver(model_store=store).resolve(self.mid,filename="m.gguf")
if __name__=="__main__":
    unittest.main()
