import yaml
from pathlib import Path
import xarray as xr
import skimage
import skimage.io


FILETYPES = dict(image=["png", "jpg", "jpeg"], netcdf=["nc", "nc4"])

DATETIME_FORMAT = "%Y%d%m%H%M"
SCENE_PATH = "scenes"
SCENE_DB_FILENAME = "scene_ids.yml"


class NoReplaceDict(dict):
    """
    dict-like object which raises exception if a key already exists when doing
    an insert
    """

    class KeyExistsException(Exception):
        pass

    def __setitem__(self, key, val):
        if key in self:
            raise self.KeyExistsException(key)
        dict.__setitem__(self, key, val)


def _make_image_scene(filepath, greyscale_threshold=0.2):
    """
    Create a cloud-mask netCDF file from an image using the `greyscale_threshold`
    """
    # TODO: make `greyscale_threshold` configurable from some external parameter
    scene_id = filepath.stem
    image = skimage.io.imread(filepath)
    image_grey = skimage.color.rgb2gray(image)
    cloud_mask = image_grey > greyscale_threshold
    da = xr.DataArray(cloud_mask)
    filepath_scene = Path(filepath).parent / SCENE_PATH / f"{scene_id}.nc"
    filepath_scene.parent.mkdir(exist_ok=True, parents=True)
    da.to_netcdf(filepath_scene)
    return scene_id, filepath_scene


def _make_netcdf_scenes(filepath):
    scenes = NoReplaceDict()
    # TODO: support for picking a single variable from a dataset
    da = xr.open_dataarray(filepath)

    def _individual_scenes_in_file():
        # TODO: support for usign 1D variables which align with the data but
        # aren't coordinates
        if "scene_id" in da.coords:
            for scene_id in da.scene_id.values:
                yield (scene_id, da.sel(scene_id=scene_id))
        elif "time" in da or "time" in da.coords:
            times_str = da.time.dt.strftime(DATETIME_FORMAT)
            for time in da.time.values:
                time_str = times_str.sel(time=time).item()
                filename_stem = filepath.stem
                scene_id = f"{filename_stem}__{time_str}"
                yield (scene_id, da.sel(time=time))
        else:
            raise NotImplementedError(
                "When using a netCDF file as source it should either"
                "have a `scene_id` or `time` 1D coordinate defined"
            )

    for scene_id, da_scene in _individual_scenes_in_file():
        filename_scene = f"{scene_id}.nc"
        filepath_scene = filepath.parent / SCENE_PATH / filename_scene
        filename_scene.parent.mkdir(exist_ok=True, parents=True)
        da_scene.to_netcdf(filepath_scene)
        scenes[scene_id] = filepath_scene

    return scenes


def make_scenes(data_path):
    """
    Look for images and netCDF files in `data_path` and generate scene IDs (and
    individual scene netCDF-files where the netCDF files contain multiple
    scenes). Returns a dictionary mapping the scene ids to the filename
    containing the scene data.

    The scene ids are generated as follows:
        images: the filename stem is used
        netCDF: the `scene_id` coordinate value is used if defined, otherwise
                the `time` coordinate is formatted into string
    """
    filepaths_by_filetype = {}
    for filetype, extensions in FILETYPES.items():
        for file_ext in extensions:
            filepaths_ext = list(data_path.glob(f"*.{file_ext}"))
            if len(filepaths_ext) > 0:
                filepaths_type = filepaths_by_filetype.setdefault(filetype, [])
                filepaths_type += filepaths_ext

    if len(filepaths_by_filetype) == 0:
        raise FileNotFoundError(f"No valid source files found in `{data_path}`")

    scenes = NoReplaceDict()

    for filetype, filepaths in filepaths_by_filetype.items():
        if filetype == "image":
            for filepath in filepaths:
                scene_id, filepath_scene = _make_image_scene(filepath=filepath)
                scenes[scene_id] = filepath_scene
        elif filetype == "netcdf":
            for filepath in filepaths:
                scenes.update(_make_netcdf_scenes(filepath=filepath))
        else:
            raise NotImplementedError(filetype)

    # turn into a regular dict and make paths into strings
    scenes = dict(scenes)
    for scene_id, filepath in scenes.items():
        scenes[scene_id] = str(filepath)

    return scenes


def produce_scene_ids(data_path, dst_filename=SCENE_DB_FILENAME):
    scenes = make_scenes(data_path=data_path)

    with open(data_path / SCENE_PATH / dst_filename, "w") as fh:
        yaml.dump(scenes, fh, default_flow_style=False)


if __name__ == "__main__":
    import argparse

    argparser = argparse.ArgumentParser()
    argparser.add_argument("--data-path", default=".", type=Path)
    args = argparser.parse_args()

    produce_scene_ids(**vars(args))
