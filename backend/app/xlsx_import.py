from io import BytesIO
from re import match
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

HEADERS=('product_name','category','description','tone','sku','option_label','unit','price','min_qty','step','max_qty')
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL_NS='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL_NS='http://schemas.openxmlformats.org/package/2006/relationships'

def _xml(archive,name):
    try:data=archive.read(name)
    except KeyError:raise ValueError('The workbook is missing required Excel data.')
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('The workbook contains unsupported XML declarations.')
    return ET.fromstring(data)

def _column(reference):
    letters=''.join(x for x in reference if x.isalpha()).upper()
    value=0
    for letter in letters:value=value*26+ord(letter)-64
    return value-1

def product_rows(payload):
    if len(payload)>5_000_000:raise ValueError('The Excel file must be 5 MB or smaller.')
    try:
        with ZipFile(BytesIO(payload)) as archive:
            if sum(x.file_size for x in archive.infolist())>25_000_000:raise ValueError('The expanded workbook is too large.')
            strings=[]
            if 'xl/sharedStrings.xml' in archive.namelist():
                root=_xml(archive,'xl/sharedStrings.xml')
                strings=[''.join(node.text or '' for node in item.iter(f'{{{NS}}}t')) for item in root.findall(f'{{{NS}}}si')]
            workbook=_xml(archive,'xl/workbook.xml')
            sheet=next((x for x in workbook.findall(f'.//{{{NS}}}sheet') if x.attrib.get('name')=='Products'),None)
            if sheet is None:raise ValueError('The workbook must contain a sheet named Products.')
            relation_id=sheet.attrib.get(f'{{{REL_NS}}}id')
            relations=_xml(archive,'xl/_rels/workbook.xml.rels')
            relation=next((x for x in relations.findall(f'{{{PKG_REL_NS}}}Relationship') if x.attrib.get('Id')==relation_id),None)
            if relation is None:raise ValueError('The Products sheet could not be located.')
            target=relation.attrib['Target'].lstrip('/')
            sheet_path=target if target.startswith('xl/') else 'xl/'+target
            root=_xml(archive,sheet_path)
            rows=[]
            for row in root.findall(f'.//{{{NS}}}row'):
                values=['']*len(HEADERS)
                for cell in row.findall(f'{{{NS}}}c'):
                    index=_column(cell.attrib.get('r',''))
                    if index<0 or index>=len(HEADERS):continue
                    kind=cell.attrib.get('t')
                    if kind=='inlineStr':value=''.join(x.text or '' for x in cell.iter(f'{{{NS}}}t'))
                    else:
                        node=cell.find(f'{{{NS}}}v');value=node.text if node is not None and node.text is not None else ''
                        if kind=='s' and value:value=strings[int(value)]
                    values[index]=value.strip() if isinstance(value,str) else value
                if any(value!='' for value in values):rows.append(values)
    except BadZipFile:raise ValueError('Upload a valid .xlsx Excel workbook.')
    if not rows or tuple(str(x).strip() for x in rows[0])!=HEADERS:raise ValueError('The Products sheet headers do not match the standard template.')
    data=rows[1:]
    if not data:raise ValueError('Add at least one product row before importing.')
    if len(data)>1000:raise ValueError('A single import supports up to 1,000 selling-option rows.')
    return [dict(zip(HEADERS,row)) for row in data]
