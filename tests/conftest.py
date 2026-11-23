"""Test setup: a minimal stand-in for NiFi's `nifiapi` package.

The real package only exists inside a NiFi install. The processor imports four
names from it; these stubs provide just enough to instantiate the class and call
transform() outside NiFi.
"""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "processors"))
sys.path.insert(0, str(ROOT / "scripts"))


class FlowFileTransform:
    def __init__(self, **kwargs):
        self.logger = StubLogger()


class FlowFileTransformResult:
    def __init__(self, relationship, contents=None, attributes=None):
        self.relationship = relationship
        self.contents = contents
        self.attributes = attributes or {}


class PropertyDescriptor:
    def __init__(self, name, description="", required=False, default_value=None, validators=None):
        self.name = name
        self.description = description
        self.required = required
        self.default_value = default_value
        self.validators = validators or []


class StandardValidators:
    NON_EMPTY_VALIDATOR = "NON_EMPTY_VALIDATOR"


class StubLogger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)


flowfiletransform = types.ModuleType("nifiapi.flowfiletransform")
flowfiletransform.FlowFileTransform = FlowFileTransform
flowfiletransform.FlowFileTransformResult = FlowFileTransformResult

properties = types.ModuleType("nifiapi.properties")
properties.PropertyDescriptor = PropertyDescriptor
properties.StandardValidators = StandardValidators

nifiapi = types.ModuleType("nifiapi")
nifiapi.flowfiletransform = flowfiletransform
nifiapi.properties = properties

sys.modules.setdefault("nifiapi", nifiapi)
sys.modules.setdefault("nifiapi.flowfiletransform", flowfiletransform)
sys.modules.setdefault("nifiapi.properties", properties)
