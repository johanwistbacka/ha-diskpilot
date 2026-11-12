import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const source=await readFile(new URL('../custom_components/dishwasher_optimizer/www/profile-registration.js',import.meta.url),'utf8');
const {zonedTimestamp}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const valid=[
  ['Europe/Stockholm','2026-11-11T23:00','2026-11-11T22:00:00.000Z'],
  ['Europe/Stockholm','2026-07-11T23:00','2026-07-11T21:00:00.000Z'],
  ['Europe/Stockholm','2026-12-31T23:59:59','2026-12-31T22:59:59.000Z'],
  ['UTC','2026-01-01T00:00','2026-01-01T00:00:00.000Z'],
  ['America/New_York','2026-01-01T00:00','2026-01-01T05:00:00.000Z'],
  ['America/New_York','2026-07-01T00:00','2026-07-01T04:00:00.000Z'],
  ['Asia/Kathmandu','2026-01-01T00:00','2025-12-31T18:15:00.000Z'],
  ['Australia/Lord_Howe','2026-01-01T00:00','2025-12-31T13:00:00.000Z'],
  ['Australia/Lord_Howe','2026-07-01T00:00','2026-06-30T13:30:00.000Z'],
];
for(const[zone,local,expected]of valid)test(`HA zone: ${zone} ${local}`,()=>assert.equal(zonedTimestamp(local,zone),expected));
const invalid=[
  ['Europe/Stockholm','2026-03-29T02:30'],
  ['Europe/Stockholm','2026-10-25T02:30'],
  ['America/New_York','2026-03-08T02:30'],
  ['America/New_York','2026-11-01T01:30'],
  ['Australia/Lord_Howe','2026-04-05T01:45'],
  ['Australia/Lord_Howe','2026-10-04T02:15'],
  ['UTC','2026-02-30T12:00'],
  ['UTC',''],
  ['UTC','not-a-date'],
];
for(const[zone,local]of invalid)test(`Reject invalid or ambiguous: ${zone} ${local}`,()=>assert.throws(()=>zonedTimestamp(local,zone)));
