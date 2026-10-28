import {readFileSync, writeFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const archive=JSON.parse(readFileSync('backend/app/data/archive-source.json','utf8'));
const NativeDate=Date;
class AnchorDate extends NativeDate { constructor(...args){super(...(args.length?args:['2026-10-28T00:00:00Z']))} static now(){return new NativeDate('2026-10-28T00:00:00Z').getTime()} }
const out={provenance:{archiveSha256:archive.sha256,anchor:archive.anchor,classification:'authored archive examples; not evaluated metrics'}};
for(const [key,path] of [['ao02','src/data/mockAO02Dataset.ts'],['legacy','src/data/mockData.ts']]){
 const source=archive.sources[path].replace(/import\s+[\s\S]*?from\s+['"][^'"]+['"];?/g,'');
 const names=[...source.matchAll(/export\s+(?:const|function)\s+(\w+)/g)].map(m=>m[1]);
 const js=stripTypeScriptTypes(source,{mode:'transform'}).replace(/export\s+/g,'');
 const values=new Function('Date', js+'\nreturn {'+names.join(',')+'}')(AnchorDate);
 if(values.generate12MonthTimeSeries){ values.timeSeries=Object.fromEntries(['STORAGE','POWER','NETWORK','THERMAL_COOLING'].map(r=>[r,values.generate12MonthTimeSeries(r)]));delete values.generate12MonthTimeSeries; }
 out[key]=values;
}
writeFileSync('backend/app/data/archive.json',JSON.stringify(out));
console.log('Preserved archive datasets',Object.keys(out.ao02),Object.keys(out.legacy));
