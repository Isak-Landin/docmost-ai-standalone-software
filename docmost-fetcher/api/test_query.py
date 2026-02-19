import os
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import jsonify

from datetime import datetime

DB_URL="postgresql://docmost:STRONG_DB_PASSWORD@64.112.126.69:54327/docmost"
DB_HOST="db"
DB_PORT="54327"
DB_NAME="docmost"
DB_USER="docmost"
DB_PASS=""


def _conn():
    return psycopg2.connect(
        DB_URL,
        cursor_factory=RealDictCursor
    )

def get_spaces(space_id = None) -> dict[str, Any]:
    # Dict[str, Dict[str, str, datetime, datetime, str]]
    _space_id = space_id
    if _space_id:
        sql = """
            SELECT id, name, created_at, updated_at, visibility
            FROM public.spaces
            WHERE id = %s
              AND deleted_at IS NULL
            ORDER BY created_at ASC
        """
        params = (_space_id,)
    else:
        sql = """
            SELECT id, name, created_at, updated_at, visibility
            FROM public.spaces
            WHERE deleted_at IS NULL
            ORDER BY created_at ASC
        """
        params = None

    with _conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)

            rows = cur.fetchall()
            if not rows:
                return {}

            contents = {}

            for row in rows:
                contents[row["id"]] = {
                    "name": row["name"], "created_at": row["created_at"], "updated_at": row["updated_at"], "visibility": row["visibility"]
                }
            return contents


def get_pages_in_space(dict_space_id) -> dict[str, Any]:
    """
    Expects format from get_spaces, this is important in case of direct usage from get_pages_content

    @dict_space_id -
        {
            space_id: {
                name: string,
                created_at: Datetime,
                updated_at: Datetime,
                visibility: string
            },
            // if get_spaces called without id, all pages below will be presented too, else only first match
            space_id: {
                name: string,
                created_at: Datetime,
                updated_at: Datetime,
                visibility: string
            },
            space_id: {
                name: string,
                created_at: Datetime,
                updated_at: Datetime,
                visibility: string
            },
            space_id: {
                name: string,
                created_at: Datetime,
                updated_at: Datetime,
                visibility: string
            }
        }
    """
    _space_id = None
    _error_holder = []
    contents = {}
    for key, value in dict_space_id.items():
        if not _space_id:
            if not value:
                value = None
            # TODO ensure it no longer uses external error key, deprecated, use internal error inside object
            _error_holder.append(
                {
                    "error": "No space_id provided",
                    "message": "We expected",
                    "key": _space_id,
                    "value": value
                }
            )
        sql = f"""
            SELECT id, title, parent_page_id, creator_id, space_id, created_at, updated_at
            FROM public.pages
            WHERE space_id = %s
                AND deleted_at IS NULL
            ORDER BY created_at ASC
        """

        params = (_space_id,)

        with _conn() as c:
            with c.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

                if not rows:
                    contents[_space_id] = None
                else:
                    for row in rows:
                        contents[_space_id][row["id"]] = {
                            "title": row["title"],
                            "parent_page_id": row["parent_page_id"],
                            "creator_id": row["creator_id"],
                            "space_id": row["space_id"],
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        }
    if _error_holder:
        for _json_object in _error_holder:
            contents.update(_json_object)
    return contents

def get_pages_content (page_ids_space: Dict = None, space_id: str = None):
    """
    Expects format from get_pages_in_space, should use directly if not passed from ui
    {
        space_id: {
            page_id: {
                title: string,
                parent_page_id: string,
                creator_id: string,
                space_id: string,
                created_at: Datetime,
                updated_at: Datetime,
            },
            page_id: {
                title: string,
                parent_page_id: string,
                creator_id: string,
                space_id: string,
                created_at: Datetime,
                updated_at: Datetime,
            }
        },
        space_id: {
            page_id: {
                title: string,
                parent_page_id: string,
                creator_id: string,
                space_id: string,
                created_at: Datetime,
                updated_at: Datetime,
            }
        }
    }
    """
    _page_ids_space = page_ids_space
    _space_id = space_id
    contents = {}

    target = None

    if not _page_ids_space:
        if not _space_id:
            return {
                "error": "Missing both page_ids_space (page ids in list) and _space_id",
                "message": "Must provide space_id or list of space_ids (_page_ids_space)"
            }

        _space_dict = get_spaces(_space_id)
        if not _space_dict:
            return {
                "error": f"No result for _space_id",
                "message": f"When querying for the space information, we could not find any result for {_space_id}"
            }

        if "error" in _space_dict:
            try:
                value = _space_dict["error"]
            except KeyError:
                value = None
            return {
                "error": f"Getting space dict from space_id rendered an error or did not find any results",
                "message": "Make sure that the space_id exists",
                "value": value
            }

        _pages_in_space = None
        try:
            _pages_in_space = get_pages_in_space(_space_dict)

            if not _pages_in_space or "error" in _pages_in_space:
                _value = None
                if "error" in _pages_in_space:
                    _value = _space_dict["error"]

                return {
                    "error": f"No result for get_pages_in_space({_space_id})",
                    "message": "When running function to get pages in space from docmost db. We ran into an issue",
                    "value": _value
                }
        except KeyError as e:
            return {
                "error": f"{str(e)} - {_pages_in_space}",
                "message": "Make sure that the space_id exists"
            }

    return contents


def check_and_return_errors_in_dict(_dict_to_verify, custom_message = None, custom_value = None, custom_error = None):
    """
    Takes a dict and optional custom message and value. Dict is looked in to find references to error,
    optional message and value are used to create custom error messages if an error is found.

    It is created to be compatible with deprecated versions by looking for error key as well as error value.
    New versions should always contain error in value and NOT key.

    IT will allow error value to remain for non-deprecated dicts passed;
    where value for error is a stringified exception as e.

    TODO Ensure compatibility if passed dict contains multiple "error" keys, or values.

    @_dict_to_verify Dict
    @custom_message String
    @custom_value String
    @custom_error_message String

    @return Dict[str, str]
    """

    """
    Inspect targets of interest
    @frame
    - @f_back       - next outer frame object (this frame’s caller)
    - @f_code       - code object being executed in this frame
    - @f_lineno     - current line number in Python source code
    
    traceback
    - @tb_frame     - frame object at this level
    - @tb_lineno    - current line number in Python source code
    """

    def create_message(_dict_to_inspect):
        """
        Two base cases exist.
        One where a dict is passed with deprecated structure, using "error" as key for json object.
        Second where a dict is passed with expected structure, error as part of the values with corresponding field.

        Expected structure:
        @_dict_to_inspect Dict - is passed by caller and to be inspected
        """
        _error_message = ""
        if "error" in key:

            try:
                _error_message = _dict_to_inspect["message"]
            except KeyError:
                if not custom_message:
                    _error_message = ""
                else:
                    _error_message = custom_message
            return _error_message

        if "error" in _dict_to_inspect:
            return None
        else:
            return None

    def create_value(_dict_to_inspect):
        """
        Two base cases exist.
        One where a dict is passed with deprecated structure, using "error" as key for json object.
        Second where a dict is passed with expected structure, error as part of the values with corresponding field.

        Expected structure:
        @_dict_to_inspect Dict - is passed by caller and to be inspected
        """
        _error_value = ""
        if "error" not in _dict_to_inspect:
            try:
                _error_value = _dict_to_inspect["value"]
            except KeyError:
                if not custom_value:
                    _error_value = ""
                else:
                    _error_value = custom_value
            return _error_value
        if "error" in _dict_to_inspect:
            return None
        else:
            return None

    def create_error(_dict_to_inspect):
        """
        Two base cases exist.
        One where a dict is passed with deprecated structure, using "error" as key for json object.
        Second where a dict is passed with expected structure, error as part of the values with corresponding field.

        Expected structure:
        @_dict_to_inspect Dict - is passed by caller and to be inspected
        """
        _error_error = ""

        if "error" not in _dict_to_inspect:
            try:
                _error_error = _dict_to_inspect["error"]
            except KeyError:
                if not custom_error:
                    _error_error = ""
                else:
                    _error_error = custom_error
            return _error_error
        if "error" in _dict_to_inspect:
            return None
        else:
            return None

    _error_key_occurrences = 0
    _error_value_occurrences = 0
    for key, value in _dict_to_verify.items():
        if key == "error":
            _error_key_occurrences += 1
        if value == "error":
            _error_value_occurrences += 1

    _error_dict = {}
    for key, value in _dict_to_verify.items():
        if "error" in key or "error" in value:
            _error_dict = _dict_to_verify["error"]
            _error_dict["message"] = create_message(_error_dict)
            _error_dict["value"] = create_value(_error_dict)
            _error_dict["error"] = create_error(_error_dict)



    return _error_dict

def build_errors_dict(custom_error: str, custom_message: str = None, custom_value: str = None):
    _error = None
    _message = None
    _value = None

    _error_dict = {}

    if custom_error:
        _error_dict["error"] = custom_error
    if custom_message:
        _error_dict["message"] = custom_message
    if custom_value:
        _error_dict["value"] = custom_value


    return _error_dict




if __name__ == '__main__':
    spaces = get_spaces("019baa5d-007c-7d12-9671-af7cf1b3061a")
    print(spaces)