"""Normalize oversized diagnostic reasons only; never repair claims or figures."""
import json

from pydantic import ValidationError


def validate_response(schema, content):
    try:
        return schema.model_validate_json(content)
    except ValidationError as error:
        issues = error.errors(include_input=False, include_url=False)
        if not issues or any(i['type'] != 'string_too_long' or i['loc'][-1] != 'reason' for i in issues):
            raise
        payload = json.loads(content)
        for issue in issues:
            parent = payload
            for key in issue['loc'][:-1]:
                parent = parent[key]
            # Reasons are diagnostic summaries. All verdicts, values, dates,
            # citations and publishable Statement.text fields remain untouched.
            parent['reason'] = parent['reason'][:issue['ctx']['max_length']]
        return schema.model_validate(payload)
