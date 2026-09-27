import * as echarts from 'echarts';
import {COLORS,displayName,PERIODS,TRAILS,relativeSeries,escapeHTML} from './model.js';
const instances=new Map();
function chart(id){if(!instances.has(id)){const el=document.getElementById(id);const c=echarts.init(el);instances.set(id,c);new ResizeObserver(()=>c.resize()).observe(el);}return instances.get(id);}
const axis={axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#80909b',fontSize:10},splitLine:{lineStyle:{color:'#263039',type:'dashed'}}};
const base={backgroundColor:'transparent',animationDuration:300,textStyle:{fontFamily:'Space Grotesk, Noto Sans TC, sans-serif'},tooltip:{backgroundColor:'#1b252d',borderColor:'#42505b',textStyle:{color:'#e5e9ec',fontSize:12},confine:true}};
export function renderRotation(groups,period,mode,selected){
  const valid=groups.filter(g=>g.rotation.length),points=valid.flatMap(g=>g.rotation.slice(-TRAILS[period]));
  const extent=axisKey=>{const vals=points.map(p=>p[axisKey]);return [Math.min(98,...vals)-.4,Math.max(102,...vals)+.4];};
  const [xmin,xmax]=extent('x'),[ymin,ymax]=extent('y');
  const series=[{type:'scatter',data:[],markArea:{silent:true,label:{fontSize:10,position:'insideTopLeft'},data:[
    [{name:'改善 IMPROVING',xAxis:xmin,yAxis:100,itemStyle:{color:'#1c364344'},label:{color:'#6eaac8'}},{xAxis:100,yAxis:ymax}],
    [{name:'領先 LEADING',xAxis:100,yAxis:100,itemStyle:{color:'#1b3b3044'},label:{color:'#65c5a5'}},{xAxis:xmax,yAxis:ymax}],
    [{name:'落後 LAGGING',xAxis:xmin,yAxis:ymin,itemStyle:{color:'#46272c44'},label:{color:'#e67e83'}},{xAxis:100,yAxis:100}],
    [{name:'轉弱 WEAKENING',xAxis:100,yAxis:ymin,itemStyle:{color:'#443e2444'},label:{color:'#d3b668'}},{xAxis:xmax,yAxis:100}]]},
    markLine:{silent:true,symbol:'none',label:{show:false},lineStyle:{color:'#596169',type:'solid'},data:[{xAxis:100},{yAxis:100}]}}];
  for(const g of valid){const tail=g.rotation.slice(-TRAILS[period]),last=tail.at(-1),color=COLORS[g.sector_code]||'#aaa',emphasized=selected.has(g.id);
    series.push({type:'line',data:(mode==='arrows'?[tail[0],last]:tail).map(p=>[p.x,p.y]),showSymbol:false,silent:true,lineStyle:{color,width:emphasized?2:1,opacity:emphasized?.8:.3},z:2});
    if(tail.length>1)series.push({type:'lines',coordinateSystem:'cartesian2d',data:[{coords:mode==='arrows'?[[tail[0].x,tail[0].y],[last.x,last.y]]:[[tail.at(-2).x,tail.at(-2).y],[last.x,last.y]]}],symbol:['none','arrow'],symbolSize:6,lineStyle:{color,width:1,opacity:.7},silent:true,z:3});
    series.push({name:displayName(g),type:'scatter',data:[[last.x,last.y]],symbolSize:emphasized?10:7,itemStyle:{color,opacity:emphasized?1:.6},label:{show:emphasized,formatter:displayName(g),position:'right',fontSize:10,color:'#cdd6dc'},tooltip:{formatter:()=>`${escapeHTML(displayName(g))}<br>相對強度 ${last.x.toFixed(2)}<br>相對動能 ${last.y.toFixed(2)}<br>${last.date}`},z:4});
  }
  chart('rotation-chart').setOption({...base,grid:{left:47,right:55,top:20,bottom:45},xAxis:{...axis,type:'value',min:xmin,max:xmax,name:'RS-Ratio',nameLocation:'middle',nameGap:29,nameTextStyle:{color:'#80909b',fontSize:10},axisLabel:{...axis.axisLabel,formatter:v=>v.toFixed(1)}},yAxis:{...axis,type:'value',min:ymin,max:ymax,name:'RS-Momentum',nameTextStyle:{color:'#80909b',fontSize:10},axisLabel:{...axis.axisLabel,formatter:v=>v.toFixed(1)}},series},true);
}
export function renderRelative(groups,benchmark,period,selected){
  const chosen=groups.filter(g=>selected.has(g.id)),dates=benchmark.slice(-PERIODS[period]-1).map(p=>p.date);
  const series=chosen.map(g=>({name:displayName(g),type:'line',showSymbol:false,connectNulls:false,data:relativeSeries(g,benchmark,PERIODS[period]),lineStyle:{width:2,color:COLORS[g.sector_code]},itemStyle:{color:COLORS[g.sector_code]}}));
  series.push({name:'SPY 基準',type:'line',data:dates.map(d=>[d,100]),showSymbol:false,lineStyle:{color:'#677580',type:'dashed',width:1},tooltip:{show:false}});
  chart('relative-chart').setOption({...base,tooltip:{...base.tooltip,trigger:'axis',valueFormatter:v=>Number.isFinite(v)?v.toFixed(2):'—'},grid:{left:48,right:24,top:20,bottom:45},xAxis:{...axis,type:'category',boundaryGap:false,axisLabel:{...axis.axisLabel,formatter:v=>v.slice(5)}},yAxis:{...axis,type:'value',scale:true,axisLabel:{...axis.axisLabel,formatter:v=>v.toFixed(1)}},series},true);
}
