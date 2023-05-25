from pydantic import BaseModel, FilePath
import os
import hashlib
import os
import time
import shutil
from pathlib import Path

CACHE_FILE_FOLDER = "files"
CACHE_JSON_FNAME = "response.json"
CACHE_LAST_ACCESSED_FNAME = "last_accessed.txt"


def _calculate_file_hash(file_path):
    # Create a hash object using the SHA-256 algorithm
    hash_object = hashlib.sha256()

    # Open the file in binary mode
    with open(file_path, "rb") as f:
        # Read the file in chunks to conserve memory
        for chunk in iter(lambda: f.read(4096), b""):
            # Update the hash object with the contents of the chunk
            hash_object.update(chunk)

    # Get the hexadecimal representation of the hash
    file_hash = hash_object.hexdigest()

    return file_hash


class Cache:
    def __init__(self, cache_directory, output_spec, input_spec, cache_size=3):
        self.cache_directory = cache_directory
        if not os.path.exists(self.cache_directory):
            os.mkdir(self.cache_directory)
        self.input_spec = input_spec
        self.output_spec = output_spec
        self.cache_directory = Path(cache_directory)
        self.cache_size = cache_size

    def _get_cache_key(self, inputs):
        hashes = ""
        for key, val in inputs.dict(exclude_unset=False).items():
            if self.input_spec.__fields__[key].type_ == FilePath and val is not None:
                _calculate_file_hash(val)
            else:
                hashes += hashlib.sha256(str(val).encode()).hexdigest()

        return hashlib.sha256(hashes.encode()).hexdigest()

    def _result_is_cached(self, cache_key):
        return os.path.exists(self.cache_directory / cache_key)

    def _check_cache_integrity(self, cache_key):
        cache_json = os.path.join(self.cache_directory, cache_key, CACHE_JSON_FNAME)
        outputs = self.output_spec.parse_file(cache_json)
        for key, val in outputs.dict(exclude_unset=True).items():
            if self.output_spec.__fields__[key].type_ == FilePath:
                assert os.path.exists(
                    val
                ), f"Broken cache {cache_key}, missing file: {val}"

    def _change_root_response(self, response_json, prev_root, new_root):
        _response_dict = {}
        for key, val in response_json.dict(exclude_unset=True).items():
            if self.output_spec.__fields__[key].type_ == FilePath:
                relative_path = val.relative_to(prev_root)
                _response_dict[key] = new_root / relative_path
            else:
                _response_dict[key] = val

        return self.output_spec(**_response_dict)

    def _record_cache_access(self, cache_key):
        with open(
            os.path.join(self.cache_directory, cache_key, CACHE_LAST_ACCESSED_FNAME),
            "w",
        ) as f:
            f.write(str(time.time()))

    def _get_cache_last_accessed(self, cache_key):
        with open(
            os.path.join(self.cache_directory, cache_key, CACHE_LAST_ACCESSED_FNAME),
            "r",
        ) as f:
            return float(f.read())

    def _load_from_cache(self, cache_key, directory):
        self._check_cache_integrity(cache_key)
        cache_dir = os.path.join(self.cache_directory, cache_key)
        cache_dir_files = os.path.join(cache_dir, CACHE_FILE_FOLDER)
        cache_json = os.path.join(cache_dir, CACHE_JSON_FNAME)
        outputs = self.output_spec.parse_file(cache_json)

        shutil.copytree(cache_dir_files, directory, dirs_exist_ok=True)
        outputs = self._change_root_response(outputs, cache_dir_files, directory)
        self._record_cache_access(cache_key)
        self._maybe_clean_cache()
        return outputs

    def _delete_from_cache(self, cache_key):
        shutil.rmtree(os.path.join(self.cache_directory, cache_key))

    def _maybe_clean_cache(self):
        # Clean cache
        if len(os.listdir(self.cache_directory)) > self.cache_size:
            # Get last accessed
            cache_keys = os.listdir(self.cache_directory)
            cache_keys.sort(key=lambda x: self._get_cache_last_accessed(x))
            # Remove oldest
            for cache_key in cache_keys[: -self.cache_size]:
                self._delete_from_cache(cache_key)

    def _save_to_cache(self, cache_key, outputs: BaseModel, directory):
        cache_dir = os.path.join(self.cache_directory, cache_key)
        cache_dir_files = os.path.join(cache_dir, CACHE_FILE_FOLDER)

        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)

            shutil.copytree(directory, cache_dir_files)
            outputs_cache = self._change_root_response(
                outputs, directory, cache_dir_files
            )

            # Save response as json
            with open(os.path.join(cache_dir, CACHE_JSON_FNAME), "w") as f:
                f.write(outputs_cache.json())
        else:
            print("Cache already exists, skipping")

        self._record_cache_access(cache_key)
        self._check_cache_integrity(cache_key)
        self._maybe_clean_cache()
