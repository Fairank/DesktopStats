"""Pure memory-envelope layout; complete height never scales the PCB.

Known dimensions calibrate the existing exterior reference. They do not make
the original polygon, solid cover extrusion or3mm RGB strip manufacturing CAD.
No renderer, Qt, devices, files, threads, timers or new meshes are involved.
"""
import math

_KNOWN_TOTAL_STATUSES=('primary','derived_nominal')


def _number(value,low,high):
    return type(value) in (int,float) and math.isfinite(value) and low<=value<=high


def _pcb(module,field,legacy,default,low,high):
    value=module.get(field+'_mm')
    if module.get(field+'_status')=='primary' and _number(value,low,high):
        return float(value),'primary',module.get(field+'_source_url')
    value=module.get(legacy) if legacy else None
    if _number(value,low,high):return float(value),'legacy_reference',None
    return float(default),'default_reference',None


def _total(module,field,low,high):
    value=module.get(field+'_mm');status=module.get(field+'_status')
    if status in _KNOWN_TOTAL_STATUSES and _number(value,low,high):
        return float(value),status,module.get(field+'_source_url')
    return None,'unknown',None


def _polygon(value):
    # Match the existing case_polygon contract. Tuples or invalid points must
    # not turn an old fallback into a newly claimed model-specific contour.
    if not isinstance(value,list) or not 3<=len(value)<=512:return []
    if not all(isinstance(point,(list,tuple)) and len(point)==2
        and all(_number(v,-2.,3.) for v in point) for point in value):return []
    return [[point[0],point[1]] for point in value]


def _fallback(height):
    # Existing generic spreader: .96PCB width x .81PCB height, center+3mm.
    # This is only a reference rectangle, never a newly observed SKU shape.
    top=.095-3./height;bottom=.905-3./height
    return [[.02,top],[.98,top],[.98,bottom],[.02,bottom]]


def layout(module,short=False):
    """Return detached dimensions/polygon for the current single cover/cap.

    Local polygon X is contact-edge length; Y grows toward the PCB bottom.
    Height mapping fixes normalizedY=1 (PCB bottom), keeping every notch/zigzag
    in order. The consumer scales coverX with cover_width and coverY with the
    independent pcb_height; it must not scale both with complete module size.
    """
    module=module if isinstance(module,dict) else {};short=short is True
    width,ws,wu=_pcb(module,'pcb_length','length_mm',69.6 if short else 133.35,50.,160.)
    height,hs,hu=_pcb(module,'pcb_height','height_mm',30. if short else 31.,15.,70.)
    thickness,ts,tu=_pcb(module,'pcb_thickness',None,1.2,.05,5.)
    total,totals,totalu=_total(module,'total_height',15.,128.)
    length,lengths,lengthu=_total(module,'total_length',50.,180.)
    whole_thickness,cts,ctu=_total(module,'total_thickness',.1,30.)
    appearance=module.get('appearance');appearance=appearance if isinstance(appearance,dict) else {}
    bare=module.get('heat_spreader') is False or appearance.get('shroud')=='bare'
    has_cover=not bare
    has_cap=has_cover and (module.get('rgb_diffuser') is True or module.get('diffuser') is True)
    cap_height=3. if has_cap else 0.
    cap_center=height*.55 if has_cap else None
    polygon=_polygon(module.get('case_polygon'));issues=[];fallback=False
    if module.get('case_polygon') and not polygon:issues.append('invalid_reference_cover_polygon')
    if polygon and (max(p[0] for p in polygon)-min(p[0] for p in polygon)<=1e-9
                    or 1.-min(p[1] for p in polygon)<=1e-9):
        polygon=[];issues.append('degenerate_reference_cover_polygon')
    width_out=length if has_cover and length is not None else width
    cover_thickness=whole_thickness if whole_thickness is not None else 3.2
    applied=False
    consistent=total is not None and total+1e-8>=height+cap_height
    if has_cover and total is not None and not consistent:
        issues.append('total_height_below_pcb_and_reference_cap')
    if has_cover and consistent:
        if not polygon:polygon=_fallback(height);fallback=True
        source_top=min(p[1] for p in polygon)
        scale=(total-cap_height)/(height*(1.-source_top))
        polygon=[[x,1.+(y-1.)*scale] for x,y in polygon]
        applied=True
        if has_cap:cap_center=total-height/2.-cap_height/2.
    elif not has_cover and total is not None:
        applied=math.isclose(total,height,rel_tol=0.,abs_tol=1e-7)
        if not applied:issues.append('bare_total_differs_from_pcb_reference')
    if has_cover and length is not None and polygon:
        left=min(p[0] for p in polygon);span=max(p[0] for p in polygon)-left
        if span>1e-9:polygon=[[(x-left)/span,y] for x,y in polygon]
    # Report the resulting reference envelope rather than claiming that any
    # inconsistent legacy PCB, below-bottom source shape or cap is corrected.
    low,high=-height/2.,height/2.
    if has_cover:
        if polygon:
            values=[(.5-y)*height for _,y in polygon]
            low=min(low,min(values));high=max(high,max(values))
        else:low=min(low,3.-height*.405);high=max(high,3.+height*.405)
    if has_cap:
        low=min(low,cap_center-cap_height/2.);high=max(high,cap_center+cap_height/2.)
    matches=None if total is None else math.isclose(high-low,total,rel_tol=0.,abs_tol=1e-7)
    if applied and matches is False:issues.append('source_cover_extends_below_pcb_bottom')
    margin=max((max(-v,v-1.) for p in polygon for v in p),default=0.)
    known=dict(pcb_width=ws=='primary',pcb_height=hs=='primary',pcb_thickness=ts=='primary',
        total_height=total is not None,cover_width=has_cover and length is not None,
        cover_thickness=has_cover and whole_thickness is not None)
    return dict(pcb_width_mm=width,pcb_height_mm=height,pcb_thickness_mm=thickness,
        cover_polygon=polygon,cover_width_mm=width_out,cover_thickness_mm=cover_thickness,
        total_height_mm=total,cap_height_mm=cap_height,cap_center_from_pcb_center_mm=cap_center,
        has_cover=has_cover,has_cap=has_cap,total_height_applied=applied,
        geometry_total_height_mm=high-low,geometry_matches_total_height=matches,
        cover_polygon_is_reference_fallback=fallback,required_polygon_margin=max(2.,margin),
        cap_height_verified=False,cover_internal_cavity_modeled=False,
        cover_thickness_is_metal_sheet_measurement=False,cad_verified=False,installed_height_verified=False,
        height_mm_describes='pcb',known=known,
        reference=dict(pcb_width=ws!='primary',pcb_height=hs!='primary',pcb_thickness=ts!='primary',
                       cover_polygon=True,cap_geometry=has_cap,cover_internal_structure=True),
        dimension_status=dict(pcb_width=ws,pcb_height=hs,pcb_thickness=ts,total_height=totals,
                              cover_width=lengths if has_cover else 'no_cover',
                              cover_thickness=cts if whole_thickness is not None else 'legacy_reference'),
        source_urls=dict(pcb_width=wu,pcb_height=hu,pcb_thickness=tu,total_height=totalu,
                         cover_width=lengthu,cover_thickness=ctu),issues=tuple(issues))
