#!/usr/bin/env python
import os
import sys
import argparse
import collections
import json
from singer import metadata, get_logger
from singer.catalog import Catalog
import tty

from PyInquirer import prompt

logger = get_logger().getChild('singer-discover')

def breadcrumb_name(breadcrumb):
    name = ".".join(breadcrumb)
    name = name.replace('properties.', '')
    name = name.replace('.items', '[]')
    return name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', '-o', type=str, required=True)
    parser.add_argument('--sort', '-s', action='store_true')

    if sys.stdin.isatty():
        parser.add_argument('--input', '-i', type=str, required=True)

        args = parser.parse_args()

        with open(args.input) as f:
            catalog = json.load(f)

    else:

        args = parser.parse_args()

        catalog = json.loads(sys.stdin.read())

        sys.stdin = sys.stdout

    logger.info("Catalog configuration starting...")
    catalog = Catalog.from_dict(catalog)
    streams = catalog.streams

    if args.sort:
        streams = sorted(streams, key=lambda s: s.stream)

    select_streams = {
        'type': 'checkbox',
        'message': 'Select Streams',
        'name': 'streams',
        'choices': [
            {'name': stream.stream, 'checked': stream.is_selected()} for stream in streams
        ]
    }

    selected_streams = prompt(select_streams)

    for i, stream in enumerate(catalog.streams):

        mdata = metadata_to_map(stream.metadata)

        if stream.stream not in selected_streams['streams']:
            mdata = metadata.write(
                mdata, (), 'selected', False
            )
        else:
            mdata = metadata.write(
                mdata, (), 'selected', True
            )

            fields = []

            field_reference = {}

            keys = mdata.keys()

            if args.sort:
                keys = sorted(keys)

            for breadcrumb in keys:
                field = mdata[breadcrumb]

                if breadcrumb != ():
                    selected, disabled = False, False
                    
                    if metadata.get(mdata, breadcrumb, 'inclusion') == 'automatic':
                        selected, disabled = True, "automatic"

                    elif metadata.get(mdata, breadcrumb, 'selected-by-default'):
                        selected, disabled = True, False

                    elif metadata.get(mdata, breadcrumb, 'selected'):
                        selected, disabled = True, False

                    name = breadcrumb_name(breadcrumb)

                    field_reference[name] = breadcrumb

                    fields.append({
                        'name': name,
                        'checked': selected,
                        'disabled': disabled
                    })

            stream_options = {
                'type': 'checkbox',
                'message': 'Select fields from stream: `{}`'.format(
                    stream.stream),
                'name': 'fields',
                'choices': fields
            }

            selections = prompt(stream_options)

            selections = [
                field_reference[n] for n in selections['fields']
                if n != "Select All"
            ]

            for breadcrumb in mdata.keys():
                if breadcrumb != ():
                    if (metadata.get(mdata, breadcrumb, 'inclusion') == 'automatic'
                            and metadata.get(mdata, breadcrumb, 'selected') is not None):
                        metadata.delete(mdata, breadcrumb, 'selected')
                    
                    if breadcrumb in selections:
                        mdata = metadata.write(mdata, breadcrumb, 'selected', True)
                        
                    elif (metadata.get(mdata, breadcrumb, 'selected-by-default') 
                            or metadata.get(mdata, breadcrumb, 'selected')):
                        mdata = metadata.write(mdata, breadcrumb, 'selected', False)

            catalog.streams[i].metadata = metadata.to_list(mdata)

    logger.info("Catalog configuration saved.")

    with open(args.output, 'w') as f:
        json.dump(catalog.to_dict(), f, indent=2)


def metadata_to_map(metadata):
    return collections.OrderedDict((tuple(md['breadcrumb']), md['metadata']) for md in metadata)


if __name__ == '__main__':
    main()
