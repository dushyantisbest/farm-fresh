'use strict';
const $ = id => document.getElementById(id);
const el = (tag, value, cls) => {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (cls) node.className = cls;
  return node;
};
let state, action, orderId;
const fmt = v => Number(v).toLocaleString();
const day = v => new Date(v + 'T12:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short'});
function button(text, fn) {
  const b = el('button',text,'small'); b.type='button'; b.onclick=fn; return b;
}
function view() {
  const tab = ['inventory','orders','planning'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'overview';
  $('overview').hidden = tab !== 'overview'; $('orders').hidden = tab !== 'orders'; $('catalog').hidden = ['orders','planning'].includes(tab); $('planning').hidden = tab !== 'planning';
  $('title').textContent = {overview:'Inventory overview', planning:'Demand planning',inventory:'Inventory register',orders:'Supplier orders'}[tab];
  document.querySelectorAll('nav a').forEach(a=>{if(a.hash==='#'+tab)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
  if(state && tab==='overview') draw();
}
function render() {
  const {items,orders,trend,today}=state;
  $('date').textContent=new Date(today+'T12:00:00').toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  const sum = key => items.reduce((total,p)=>total+p[key],0);
  $('metrics').replaceChildren(...[
    ['Available stock',sum('available'),items.length+' products tracked'],
    ['Expiring soon',sum('expiring'),'Units due within 7 days'],
    ['Low stock',items.filter(p=>p.low).length,'Products at ≤3 days of demand'],
    ['Open orders',orders.filter(o=>!o.received).length,'Awaiting supplier delivery']
  ].map(([name,value,detail])=>{let box=el('div',undefined,'metric');box.append(el('b',name),el('strong',fmt(value)),el('small',detail));return box;}));
  $('figures').replaceChildren(...trend.map(t=>el('span',day(t.date)+' · '+t.units)));
  const alerts=items.filter(p=>p.expired||p.expiring||p.low).sort((a,b)=>(b.expired-a.expired)||Number(b.low)-Number(a.low)||(a.expiry||'').localeCompare(b.expiry||''));
  $('alerts').replaceChildren(...alerts.map(p=>{
    const row=el('div',undefined,'alert'), label=el('div');
    const notes=[];
    if(p.expired) notes.push(p.expired+' expired · remove from shelf');
    if(p.expiring) notes.push(p.expiring+' near expiry · review for discount');
    if(p.low) notes.push('Low stock');
    label.append(el('b',p.name),el('small',notes.join(' · ')));row.append(label);
    if(p.reorder)row.append(button('Order '+p.reorder,()=>openForm('order',p.id)));return row;
  }));
  if(!alerts.length)$('alerts').append(el('p','No stock alerts.'));
  renderPlanning(); register(); $('orderRows').replaceChildren(...orders.map(o=>{
    const r=el('tr');[o.name,o.supplier,o.qty,day(o.placed),o.received?'Received':'Open'].forEach(v=>r.append(el('td',v)));
    const cell=el('td'); if(!o.received)cell.append(button('Receive',()=>openForm('receive',o.product,o.id)));r.append(cell);return r;
  }));
  if(!orders.length)emptyRow('orderRows','No supplier orders yet. Place an order to track it here.');
  view();
}
function emptyRow(id,text){let r=el('tr'),c=el('td',text);c.colSpan=6;r.append(c);$(id).append(r);}
function renderPlanning(){
  const plan=state.planning;
  const rows=plan.plans[$('festival').value];
  $('planRows').replaceChildren(...rows.map(p=>{
    const tr=el('tr');
    for(const value of [p.name,p.normal,p.forecast,p.factor+'× · '+p.source,p.pending,p.order && p.order_by ? (p.order_by<=state.today?'Today':day(p.order_by)):'—'])tr.append(el('td',value));
    const td=el('td');
    if(p.order)td.append(button('Order '+p.order,()=>{
      openForm('order',p.id);
      $('form').elements.namedItem('qty').value=p.order;
    }));
    else td.textContent='Covered';
    tr.append(td);return tr;
  }));
  const v=plan.evaluation;
  $('validation').textContent='Trained on 2023–2024 and evaluated on '+v.cases+' synthetic product/festival weeks in '+v.year+'. Mean absolute error: '+v.festival_mae+' units with festival history, versus '+v.baseline_mae+' units using the normal week.';
}
$('festival').onchange=()=>{if(state)renderPlanning();};
function register(){
  if(!state)return;
  const filter=$('filter').value, search=$('search').value.toLowerCase().trim();
  const list=state.items.filter(p=>(!filter||p[filter])&&(p.name+' '+p.category+' '+p.supplier).toLowerCase().includes(search));
  $('rows').replaceChildren(...list.map(p=>{
    const row=el('tr'), name=el('td');name.append(el('strong',p.name),el('small',p.category+' · '+p.supplier));
    row.append(name,el('td',fmt(p.available)),el('td',p.expiry?day(p.expiry):'—'),el('td',fmt(p.demand)+' units'));
    const status=el('td');for(const [key,text,cls] of [['expired','Expired','bad'],['low','Low stock','bad'],['expiring','Near expiry','warn']])if(p[key])status.append(el('span',text,'pill '+cls));
    if(!status.childNodes.length)status.append(el('span','Healthy','pill'));
    const c=el('td');c.append(button(p.reorder?'Order '+p.reorder:'Order',()=>openForm('order',p.id)));row.append(status,c);return row;
  }));
  if(!list.length)emptyRow('rows','No products match these filters.');
}
function draw(){
  if(!state||$('overview').hidden)return;
  const canvas=$('chart'), w=canvas.clientWidth,h=152,d=devicePixelRatio||1;
  if(!w)return;canvas.width=w*d;canvas.height=h*d;
  const c=canvas.getContext('2d');c.scale(d,d);
  const data=state.trend,max=Math.max(1,...data.map(v=>v.units)), step=(w-35)/data.length;
  c.font='11px Segoe UI, sans-serif';c.fillStyle='#647268';
  for(let i=0;i<3;i++){const y=12+i*51;c.fillText(String(Math.round(max*(1-i/2))),0,y+4);c.strokeStyle='#e1e7dd';c.beginPath();c.moveTo(27,y);c.lineTo(w,y);c.stroke();}
  data.forEach((p,i)=>{const height=p.units/max*102,x=30+i*step;c.fillStyle=i===data.length-1?'#b4ce80':'#4a7960';c.fillRect(x,114-height,step*.65,height);
    if(i===0||i===6||i===13){c.fillStyle='#647268';c.fillText(day(p.date),Math.min(x,w-38),138);}
  });
}
const titles={product:'Add product',sale:'Record sale',order:'Place supplier order',receive:'Receive delivery'};
function field(name,title,type,value){
  const label=el('label',title),input=el(type==='select'?'select':'input'); input.name=name;input.required=true;
  if(type==='select'){state.items.forEach(p=>{const opt=el('option',p.name);opt.value=p.id;input.append(opt);});}
  else {input.type=type;if(type==='number'){input.min=1;input.max=1000000;}if(type==='date')input.min=state.today;if(type==='text')input.maxLength=80;}
  if(value!=null)input.value=value;label.append(input);$('fields').append(label);return input;
}
function openForm(kind,pid,oid){
  if(!state)return;action=kind;orderId=oid;$('error').textContent='';$('dialogTitle').textContent=titles[kind];$('submit').textContent=titles[kind];$('fields').replaceChildren();
  let product,qty;
  if(kind==='product'){for(const [key,name] of [['name','Product name'],['category','Category'],['supplier','Supplier']])field(key,name,'text');}
  else if(kind!=='receive')product=field('product','Product','select',pid);
  else {let o=state.orders.find(x=>x.id===oid);$('fields').append(el('p',o.name+' · '+o.qty+' units from '+o.supplier));}
  if(kind!=='receive')qty=field('qty',kind==='product'?'Opening units':'Quantity','number',1);
  if(kind==='order'){const suggest=()=>{qty.value=state.items.find(p=>p.id===Number(product.value)).reorder||1;};product.onchange=suggest;suggest();}
  if(kind==='receive'||kind==='product')field('expiry','Batch expiry date','date');
  $('dialog').showModal();
}
async function refresh(){let r=await fetch('/api/dashboard');if(!r.ok)throw Error('Unable to load inventory. Refresh to retry.');state=await r.json();render();}
$('form').onsubmit=async e=>{
  e.preventDefault();let data=Object.fromEntries(new FormData(e.target));for(const key of ['product','qty'])if(key in data)data[key]=Number(data[key]);if(action==='receive')data.order=orderId;
  $('submit').disabled=true;
  try{let r=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});let result=await r.json();if(!r.ok)throw Error(result.error);
    $('dialog').close();$('message').textContent={order:'Supplier order placed.',sale:'Sale recorded.',product:'Product added.',receive:'Delivery received.'}[action];await refresh();
  }catch(err){($('dialog').open?$('error'):$('message')).textContent=err.message;}finally{$('submit').disabled=false;}
};
$('close').onclick=()=>$('dialog').close();document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>openForm(b.dataset.action));
$('search').oninput=register;$('filter').onchange=register;window.onhashchange=view;window.onresize=draw;view();refresh().catch(e=>$('message').textContent=e.message);

