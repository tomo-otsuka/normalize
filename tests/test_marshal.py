from __future__ import absolute_import

import json
from os import environ
import pickle
import re
import unittest2

from normalize.record import Record
from normalize.record.json import from_json
from normalize.record.json import JsonRecord
from normalize.property import ListProperty
from normalize.property import ROProperty
from normalize.property import SafeProperty


class CheeseRecord(Record):
    variety = SafeProperty(isa=str)
    smelliness = SafeProperty(isa=float, check=lambda x: 0 < x < 100)


class CheeseCupboardRecord(Record):
    id = ROProperty(required=True, isa=int)
    name = SafeProperty(isa=str)
    best_cheese = SafeProperty(isa=CheeseRecord)
    cheeses = ListProperty(of=CheeseRecord)


json_data_number_types = (basestring, int, long, float)


def decode_json_number(str_or_num):
    """Returns a precise number object from a string or number"""
    if isinstance(str_or_num, basestring):
        if re.match(r'-?\d+$', str_or_num):
            return long(str_or_num)
        if not re.match(r'-?\d+(\.\d+)?([eE][\-+]?\d+)?$', str_or_num):
            raise ValueError("invalid json number: '%s'" % str_or_num)
        return float(str_or_num)
    return str_or_num


class TestRecordMarshaling(unittest2.TestCase):
    def setUp(self):
        self.primitive = {
            "id": "123",
            "name": "Fridge",
            "best_cheese": dict(variety="Gouda", smelliness="12"),
            "cheeses": [
                dict(variety="Manchego", smelliness="38"),
                dict(variety="Stilton", smelliness="82"),
                dict(variety="Polkobin", smelliness="31"),
            ],
        }

    def assertDataOK(self, ccr):
        self.assertIsInstance(ccr, CheeseCupboardRecord)
        self.assertEqual(ccr.id, 123)
        self.assertEqual(len(ccr.cheeses), 3)
        self.assertEqual(ccr.best_cheese.variety, "Gouda")
        self.assertEqual(ccr.cheeses[1].smelliness, 82)

    def assertJsonDataEqual(self, got, wanted, path=""):
        """Test that two JSON-data structures are the same.  We can't use
        simple assertEqual, because '23' and 23 should compare the same."""
        if isinstance(got, basestring):
            got = unicode(got)
        if isinstance(wanted, basestring):
            wanted = unicode(wanted)

        pdisp = path or "top level"

        if type(got) != type(wanted):
            if isinstance(got, json_data_number_types) and \
                    isinstance(wanted, json_data_number_types):
                got = decode_json_number(got)
                wanted = decode_json_number(wanted)
            else:
                raise AssertionError(
                    "types differ at %s: wanted %s, got %s" % (
                        pdisp, type(wanted).__name__, type(got).__name__
                    )
                )
        if type(got) == dict:
            all_keys = sorted(set(got) | set(wanted))
            for key in all_keys:
                if (key in got) != (key in wanted):
                    raise AssertionError(
                        "dictionary differs at %s: key %s is %s" % (
                            pdisp, key,
                            "unexpected" if key in got else "missing"
                        )
                    )
                else:
                    self.assertJsonDataEqual(
                        got[key], wanted[key], path + ("[%r]" % key)
                    )
        elif type(got) == list:
            for i in range(0, max((len(got), len(wanted)))):
                if i >= len(got) or i >= len(wanted):
                    raise AssertionError(
                        "lists differs in length at %s: got %d elements, "
                        "wanted %d" % (pdisp, len(got), len(wanted))
                    )
                else:
                    self.assertJsonDataEqual(
                        got[i], wanted[i], path + ("[%d]" % i)
                    )
        elif got != wanted:
            raise AssertionError(
                "values differ at %s: wanted %r, got %r" % (
                    pdisp, wanted, got
                )
            )
        elif "SHOW_JSON_TESTS" in environ:
            print "%s: ok (%r)" % (pdisp, got)

    def test_assertJsonDataEqual(self):
        """Answering the koan, "Who will test the tests themselves?"
        """
        float("inf")
        self.assertRaises(ValueError, decode_json_number, "inf")

        matches = (
            ("123", "123"), ("123", 123), (123, 123.0), ("123.0", 123),
            ("9223372036854775783", 2**63-25), ("-5e5", -500000),
            ({}, {}), ([], []), ({"foo": "bar"}, {"foo": "bar"}),
            ([{}, "foo", 123], [{}, "foo", 123.0]),
            ({"foo": [1, 2, 3], "bar": {"foo": "baz"}},
             {"foo": [1, 2, 3], "bar": {"foo": "baz"}}),
        )
        for a, b in matches:
            self.assertJsonDataEqual(a, b)

        mismatches = (
            (123, 124), ("foo", "bar"), (123, "foo"), (123, {}),
            ({}, 123), ([], {}), ("inf", float("inf")),
            (9.223372036854776e+18, 2**63-25),
            ({"foo": "bar"}, {"bar": "foo"}),
            ([1, 2, 3], [1, 2]), ([1, 2], [1, 2, 3]),
            ({"foo": [1, 2, 3], "bar": {"foo": "baz"}},
             {"foo": [1, 2, 3], "bar": {"foo": "bat"}}),
        )
        for a, b in mismatches:
            try:
                self.assertJsonDataEqual(a, b)
            except AssertionError:
                pass
            except ValueError:
                pass
            else:
                raise Exception("Compared equal: %r vs %r" % (a, b))

    def test_native_marshall(self):
        """Test coerce from python dicts & pickling"""
        ccr = CheeseCupboardRecord(self.primitive)
        for protocol in range(0, pickle.HIGHEST_PROTOCOL + 1):
            pickled = pickle.dumps(ccr, protocol)
            ccr_copy = pickle.loads(pickled)
            self.assertDataOK(ccr_copy)

    def test_json_marshall(self):
        """Test coerce from JSON & marshall out"""
        json_struct = json.dumps(self.primitive)
        ccr = from_json(CheeseCupboardRecord, json.loads(json_struct))
        self.assertDataOK(ccr)

        class RealWorldCCR(JsonRecord, CheeseCupboardRecord):
            pass

        ccr = RealWorldCCR.from_json(json_struct)
        self.assertDataOK(ccr)

        json_data = ccr.json_data()
        json_text = json.dumps(json_data)

        self.assertJsonDataEqual(json_data, self.primitive)