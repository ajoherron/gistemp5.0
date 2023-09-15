import xarray as xr

ghcn_filepath = 'Homogenized_T_PHA1_en_101.nc'
ds = xr.open_dataset(ghcn_filepath, decode_times=None)

print(ds)