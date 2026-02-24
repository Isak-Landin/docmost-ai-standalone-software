from uuid import UUID
import uuid
from datetime import datetime
from collections import deque
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------- #
# ------ PAGES QUERY REFACTOR FUNCTIONS -------- #
# ---------------------------------------- #
def refactor_content(_text_content):
    _last_char_list = []
    _reformated_text = ""
    for char in _text_content:
        should_append = True
        try:
            if len(_last_char_list) >= 2:
                if char == "+" and _last_char_list[-1] == "+" and _last_char_list[-2] == "+":
                    should_append = False
                elif char == "\n" and _last_char_list[-1] == "\n":
                    should_append = False
            if should_append:
                _reformated_text += char

            _last_char_list.append(char)
        except IndexError as e:
            logger.warning("Index error when refactoring text content: ", e)
            print("IndexError: ", e)
            continue
        except Exception as e:
            logger.warning(f"An Error occurred during runtime " + f"str(e)")
            print("Other error when refactoring text content: ", e)
            continue

    return _reformated_text


# ------------------------------------------------------------ #
# ------ VALIDATE FOR ROUTE OUTPUT VS SCHEMAS FUNCTIONS ------ #
# ------------------------------------------------------------ #
def _validate_against_schema(refactored_envelope: dict, schema: dict):
    """
    Validates that `data` matches the structural type mapping of `schema`.
    Uses convert_schema_to_key_value_relation_list().
    """

    if not isinstance(refactored_envelope, dict):
        return {"ok": False, "error": "not_a_dict"}

    schema_rel = convert_schema_to_key_value_relation_list(schema)
    envelope_rel = convert_schema_to_key_value_relation_list(refactored_envelope)

    # Depth check
    if len(schema_rel) != len(envelope_rel):
        logger.critical(
            f"Schema mismatch: len({schema_rel}) != len({envelope_rel})" + " ---- Took place during _validate_against_schema()"
        )
        return {
            "ok": False,
            "error": "depth_mismatch",
            "expected_depth": len(schema_rel),
            "got_depth": len(envelope_rel),
        }

    # Per-depth type validation
    for depth, (schema_level, data_level) in enumerate(zip(schema_rel, envelope_rel)):

        schema_key_types = set(schema_level[0])
        schema_value_types = set(schema_level[1])

        data_key_types = set(data_level[0])
        data_value_types = set(data_level[1])

        if not data_key_types.issubset(schema_key_types):
            return {
                "ok": False,
                "error": "key_type_mismatch",
                "depth": depth,
                "expected": list(schema_key_types),
                "got": list(data_key_types),
            }

        if not data_value_types.issubset(schema_value_types):
            return {
                "ok": False,
                "error": "value_type_mismatch",
                "depth": depth,
                "expected": list(schema_value_types),
                "got": list(data_value_types),
            }

    return {"ok": True}


def convert_schema_to_key_value_relation_list(root: dict):

    def depth(d):
        return max(depth(_v) if isinstance(_v, dict) else 0 for _v in d.values()) + 1

    def check_if_uuid_type(_uuid: str):
        try:
            uuid.UUID(_uuid)
            return True
        except Exception:
            return False

    """
    Returns a list where index d contains:
      [[key types at depth d], [value types at depth d]]
    Aggregates across all dictionaries that exist at that depth.
    """

    if not isinstance(root, dict):
        raise TypeError("root must be a dict")

    relational_list = []
    q = deque([(root, 0)])

    while q:
        dct, __depth = q.popleft()

        # Ensure relational_list has an entry for this depth
        while len(relational_list) <= __depth:
            relational_list.append([[], []])  # [key_types, value_types]

        key_types, value_types = relational_list[__depth]

        for k, v in dct.items():
            is_k_uuid = check_if_uuid_type(k)
            is_v_uuid = check_if_uuid_type(v)
            if is_k_uuid:
                key_types.append(type(uuid.UUID(k)))
            else:
                key_types.append(type(k))

            if is_v_uuid:
                value_types.append(type(uuid.UUID(v)))
            else:
                value_types.append(type(v))


            # Optional: if you also want to traverse dicts inside lists/tuples/sets
            if isinstance(v, (list, tuple, set)):
                for item in v:
                    if isinstance(item, dict):
                        q.append((item, __depth + 1))

            elif isinstance(v, dict):
                q.append((v, __depth + 1))

    return relational_list


def _validate_dict(data: dict, schema_type: str, allowed_types: tuple, schemas: dict):
    if schema_type not in allowed_types:
        logger.warning(f"Invalid schema type {schema_type}")
        return {
            "ok": False,
            "error": "invalid_schema_type",
            "allowed": list(allowed_types),
        }

    schema = schemas.get(schema_type)
    if not isinstance(schema, dict):
        logger.critical(f"Schema missing or invalid for type={schema_type}")
        return {
            "ok": False,
            "error": "schema_missing",
            "value": schema_type,
        }

    return _validate_against_schema(data, schema)