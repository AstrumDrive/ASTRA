"""Regression: real prompts must carry the complete executable and its proof tail."""
import inspect
import os
import textwrap
import types
import unittest
from unittest.mock import patch

import core.llm_client as llm

LONG_CODE = '# complete validator\n' + '# padding\n' * 2000 + "print('FINAL_PROOF_TAIL_20261006')\n"


class FullValidatorCodeContextTests(unittest.IsolatedAsyncioTestCase):
    def client(self, response='{"status":"REJECT","reasoning":"capture only"}'):
        client = llm.ASTRAIntelligence(provider='codex_cli')
        client.api_key = 'offline-test-placeholder'
        seen = []

        async def capture(system, user):
            seen.append(user)
            return response

        client._call_api = capture
        return client, seen

    async def test_reviewer_gets_complete_code_beyond_old_14000_cut(self):
        client, seen = self.client()
        await client.review_validation_code('claim', 'definitions', LONG_CODE)
        self.assertIn(LONG_CODE, seen[0])

    async def test_correction_author_gets_complete_code_beyond_old_16000_cut(self):
        client, seen = self.client("print('ready')")
        with patch.dict(os.environ, {'ASTRA_VALIDATOR_REPAIR_VNEXT': '1'}):
            await client.translate_to_code('claim', True, 'failure', LONG_CODE)
        self.assertIn(LONG_CODE, seen[0])

    async def test_analyst_gets_complete_code_beyond_old_16000_cut(self):
        client, seen = self.client('{"status":"CODE_ERROR","reasoning":"capture only"}')
        await client.analyze_results('claim', {
            'validation_code': LONG_CODE, 'stdout': '', 'stderr': '', 'exit_code': 1,
        })
        self.assertIn(LONG_CODE, seen[0])

    async def test_bounded_repair_keeps_whole_code_and_instruction_tail(self):
        client, seen = self.client('{"status":"CANNOT_PATCH","reason":"capture only","edits":[]}')
        instructions = 'x' * 4000 + '\nDECISIVE_REPAIR_TAIL'
        await client.repair_validation_code('claim', LONG_CODE, instructions)
        self.assertIn(LONG_CODE, seen[0])
        self.assertIn(instructions, seen[0])

    async def test_original_cuts_make_the_same_guards_red(self):
        cases = [
            ('review_validation_code', '{code}', '{code[:14000]}'),
            ('translate_to_code', '{previous_code}', '{previous_code[:16000]}'),
            ('analyze_results', "{exec_result.get('validation_code') or ''}", "{(exec_result.get('validation_code') or '')[:16000]}"),
        ]
        for name, old, broken in cases:
            with self.subTest(method=name):
                source = textwrap.dedent(inspect.getsource(getattr(llm.ASTRAIntelligence, name)))
                self.assertIn(old, source)
                namespace = {}
                exec(source.replace(old, broken), llm.__dict__, namespace)
                client, seen = self.client("print('ready')" if name == 'translate_to_code' else '{"status":"CODE_ERROR","reasoning":"capture only"}')
                method = types.MethodType(namespace[name], client)
                with patch.dict(os.environ, {'ASTRA_VALIDATOR_REPAIR_VNEXT': '1'}):
                    if name == 'review_validation_code':
                        await method('claim', 'definitions', LONG_CODE)
                    elif name == 'translate_to_code':
                        await method('claim', True, 'failure', LONG_CODE)
                    else:
                        await method('claim', {'validation_code': LONG_CODE, 'exit_code': 1})
                with self.assertRaises(AssertionError):
                    self.assertIn(LONG_CODE, seen[0])


if __name__ == '__main__':
    unittest.main()
