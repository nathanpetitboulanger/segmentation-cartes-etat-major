"""Writers for the files the build steps produce, shared by build_raw and build_interim."""

from pathlib import Path

import geopandas as gpd
import rasterio

GDAL_TYPES = {"uint8": "Byte", "uint16": "UInt16"}
ROW_GROUP = 50_000


def write_geoparquet(gdf: gpd.GeoDataFrame, dst: Path) -> None:
    """GeoParquet 1.1, ZSTD level 9, with a bbox covering column so readers (DuckDB,
    geopandas) can skip row groups outside a window. Written to `.part` then renamed."""
    part = dst.with_name(dst.name + ".part")
    gdf.to_parquet(
        part,
        compression="zstd",
        compression_level=9,
        schema_version="1.1.0",
        write_covering_bbox=True,
        row_group_size=ROW_GROUP,
    )
    part.rename(dst)


def write_vrt(tifs: list[Path], dst: Path) -> None:
    """A mosaic of `tifs` (same resolution, CRS, bands and type), paths relative to the VRT.

    The nodata value and colour table of the first tile are carried over.
    """
    with rasterio.open(tifs[0]) as d:
        res, crs, count = d.res, d.crs, d.count
        dtype, nodata, colorinterp = d.dtypes[0], d.nodata, d.colorinterp
        colormaps = [_colormap(d, band) for band in range(1, count + 1)]
    tiles = []
    for p in tifs:
        with rasterio.open(p) as d:
            assert (d.res, d.crs, d.count, d.dtypes[0]) == (res, crs, count, dtype), (
                f"{p.name} differs from {tifs[0].name}"
            )
            tiles.append(
                (p.relative_to(dst.parent).as_posix(), d.bounds, d.width, d.height)
            )
    left = min(b.left for _, b, _, _ in tiles)
    top = max(b.top for _, b, _, _ in tiles)
    width = round((max(b.right for _, b, _, _ in tiles) - left) / res[0])
    height = round((top - min(b.bottom for _, b, _, _ in tiles)) / res[1])

    lines = [
        f'<VRTDataset rasterXSize="{width}" rasterYSize="{height}">',
        f'  <SRS dataAxisToSRSAxisMapping="1,2">{crs.to_wkt()}</SRS>',
        f"  <GeoTransform>{left}, {res[0]}, 0, {top}, 0, {-res[1]}</GeoTransform>",
    ]
    for band, (ci, cmap) in enumerate(zip(colorinterp, colormaps), 1):
        lines.append(f'  <VRTRasterBand dataType="{GDAL_TYPES[dtype]}" band="{band}">')
        if nodata is not None:
            lines.append(f"    <NoDataValue>{nodata:g}</NoDataValue>")
        lines.append(f"    <ColorInterp>{ci.name.capitalize()}</ColorInterp>")
        if cmap:
            lines.append("    <ColorTable>")
            lines += [
                f'      <Entry c1="{r}" c2="{g}" c3="{b}" c4="{a}"/>'
                for r, g, b, a in (cmap[i] for i in range(max(cmap) + 1))
            ]
            lines.append("    </ColorTable>")
        for name, b, w, h in tiles:
            x, y = round((b.left - left) / res[0]), round((top - b.top) / res[1])
            lines += [
                "    <SimpleSource>",
                f'      <SourceFilename relativeToVRT="1">{name}</SourceFilename>',
                f"      <SourceBand>{band}</SourceBand>",
                f'      <SrcRect xOff="0" yOff="0" xSize="{w}" ySize="{h}"/>',
                f'      <DstRect xOff="{x}" yOff="{y}" xSize="{w}" ySize="{h}"/>',
                "    </SimpleSource>",
            ]
        lines.append("  </VRTRasterBand>")
    lines.append("</VRTDataset>")
    dst.write_text("\n".join(lines) + "\n")


def _colormap(d, band: int) -> dict | None:
    try:
        return d.colormap(band)
    except ValueError:
        return None
