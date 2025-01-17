import xarray as xr
import skimage


def rgb_greyscale_mask(da_scene, greyscale_threshold=0.2):
    """
    Turn scene of true-colour RGB data (in xr.DataArray) into greyscale and
    apply threshold to produce a poor-man's cloud mask
    """
    image_grey = skimage.color.rgb2gray(da_scene)
    cloud_mask = image_grey > greyscale_threshold
    da_cloudmask = xr.DataArray(cloud_mask)
    return da_cloudmask
