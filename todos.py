#!/usr/bin/python

import argparse
import datetime
import json
import os

basedir = os.path.dirname(os.path.realpath(__file__))
filepath = os.path.join(basedir, 'todos.txt')

class SchemaError(Exception):
    pass

class Rule(object):
    def check(self, target):
        raise NotImplementedError

class String(Rule):
    def __init__(self, max_length):
        self.max_length = max_length

    def check(self, target):
        return isinstance(target, str) and len(target) <= self.max_length

class Date(Rule):
    def check(self, target):
        parsed = None
        try:
            parsed = datetime.datetime.strptime(target, '%Y/%m/%d')
        except ValueError:
            pass
        return parsed != None

class Priority(Rule):
    def __init__(self):
        self.types = ['minor', 'major']
    def check(self, target):
        return target in self.types

class Record(object):
    schema = {
        'ordered_keys': ['name', 'due_date', 'priority'],
        'name': String(20),
        'due_date': Date(),
        'priority': Priority()
    }

    def __init__(self, name, due_date, priority, done=False, modifications=[], original=None):
        self.name = name
        self.due_date = due_date
        self.priority = priority
        self.done = done
        self.modifications = modifications
        self.original = {
            'name': self.name,
            'due_date': self.due_date,
            'priority': self.priority,
            'done': self.done
        } if not original else original

    def mark_done(self):
        self.done = True
        self.modifications.append({'done': True})

    def modify(self, modifications):
        _modifications = {}
        for modification in modifications:
            checked = Record.check(modification)
            if checked:
                key, value = checked
                _modifications[key] = value
                setattr(self, key, value)
        self.modifications.append(_modifications)

    def print_w_changes(self):
        self.print_wo_changes()
        self._print_changes()

    def print_wo_changes(self):
        if self.done:
            print '\033[32m{0: <20} {1} {2}\033[0m'.format(self.name, self.due_date, self.priority)
        else:
            print '\033[31m{0: <20} {1} {2}\033[0m'.format(self.name, self.due_date, self.priority)

    def _print_changes(self):
        for i in xrange(len(self.modifications)-1, -1, -1):
            after = self.modifications[i]
            for key, value in after.iteritems():
                before = self._value_before(key, i-1)
                print '  {0}: \033[31m{1} \033[0m-> \033[32m{2}\033[0m'.format(key, before, value)

    def _value_before(self, key, index):
        for i in xrange(index, -1, -1):
            value = self.modifications[i].get(key, None)
            if value:
                return value
        return self.original[key]

    def write(self):
        return json.dumps({
            'name': self.name,
            'due_date': self.due_date,
            'priority': self.priority,
            'done': self.done,
            'original': self.original,
            'modifications': self.modifications
        })

    @staticmethod
    def load(item):
        obj = json.loads(item)
        return Record(obj['name'], obj['due_date'], obj['priority'], obj['done'], obj['modifications'], obj['original'])

    @classmethod
    def parse(cls, item):
        parsed = {}
        splitted = item.split(';')
        if len(splitted) != len(cls.schema.keys()) - 1:
            raise SchemaError('Item does not fit schema: {0}'.format(item))
        ordered_keys = cls.schema['ordered_keys']
        for i in xrange(len(splitted)):
            field = splitted[i]
            if (cls.schema[ordered_keys[i]].check(field)):
                parsed[ordered_keys[i]] = field
            else:
                raise SchemaError('Rule check failed on field: {0}'.format(field))
        return Record(parsed['name'], parsed['due_date'], parsed['priority'])

    @classmethod
    def check(cls, item):
        parts = item.split(':')
        if len(parts) != 2:
            return None
        key, value = parts
        if key in cls.schema.keys():
            return (key, value)
        return None

class Records(object):
    def __init__(self):
        self.records = []

    def find(self, name):
        for record in self.records:
            if record.name == name:
                return record
        return None

    def add(self, record):
        self.records.append(record)

    def add_all(self, items):
        for item in items:
            self.add(Record.parse(item))

    def remove(self, record):
        self.records.remove(record)

    def remove_all(self, items):
        for item in items:
            parts = Records._split(item, max_len=1)
            if parts:
                record = self.find(parts[0])
                if record:
                    self.remove(record)

    def mark_done_all(self, items):
        for item in items:
            parts = Records._split(item, max_len=1)
            if parts:
                record = self.find(parts[0])
                if record:
                    record.mark_done()

    def modify_all(self, items):
        for item in items:
            parts = Records._split(item)
            record = self.find(parts[0])
            if record:
                record.modify(parts[1:])

    def list_w_changes(self):
        for record in self.records:
            record.print_w_changes()

    def list_wo_changes(self):
        for record in self.records:
            record.print_wo_changes()

    def save(self):
        with open(filepath, 'w') as f:
            for record in self.records:
                f.write(record.write())
                f.write('\n')

    @staticmethod
    def _split(item, max_len=None):
        splitted = item.split(';')
        if not max_len or len(splitted) <= max_len:
            return splitted
        else:
            return None

    @staticmethod
    def load():
        records = Records()
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                for line in f:
                    records.add(Record.load(line))
        return records

def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--list', action='store_true', help='List todos.')
    parser.add_argument('-c', '--changes', action='store_true', help='Show record changes for todos. Only works with list.')
    parser.add_argument('-a', '--add', nargs='*', default=[], help='Add records. Schema: name;due_date;priority')
    parser.add_argument('-r', '--remove', nargs='*', default=[], help='Remove records. Schema: name')
    parser.add_argument('-d', '--done', nargs='*', default=[], help='Mark records done. Schema: name')
    parser.add_argument('-m', '--modify', nargs='*', default=[], help='Modify records. Schema: name;key:value;')
    return parser

def main():
    args = cli().parse_args()
    records = Records.load()
    records.add_all(args.add)
    records.remove_all(args.remove)
    records.modify_all(args.modify)
    records.mark_done_all(args.done)
    if args.list:
        if args.changes:
            records.list_w_changes()
        else:
            records.list_wo_changes()
    records.save()

if __name__ == '__main__':
    main()
