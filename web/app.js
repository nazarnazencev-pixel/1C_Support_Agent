const sid=localStorage.wizardSession||crypto.randomUUID();localStorage.wizardSession=sid;
const box=document.getElementById('messages'), input=document.getElementById('input');
function add(text,type='bot'){const d=document.createElement('div');d.className='msg '+type;d.textContent=text;box.appendChild(d);box.scrollTop=box.scrollHeight;return d}
async function init(){try{const r=await fetch(`/api/chat/${sid}/greeting`,{method:'POST'});const j=await r.json();add(j.answer||'Здравствуйте!');}catch(e){add('Не удалось подключить ИИ. Проверьте GigaChat и .env.','system')}}
async function send(){const text=input.value.trim();if(!text)return;input.value='';add(text,'user');const t=performance.now(),typing=add('ИИ печатает…','bot typing');try{const r=await fetch(`/api/chat/${sid}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});const j=await r.json();typing.remove();add(j.answer||j.detail||'Нет ответа',r.ok?'bot':'system');}catch(e){typing.remove();add('Ошибка соединения с сервером.','system')}console.log('response',Math.round(performance.now()-t),'ms')}
input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
async function specialist(){const r=await fetch(`/api/chat/${sid}/specialist`,{method:'POST'});const j=await r.json();add(j.message||'Запрос специалисту отправлен.','system')}
function requestSpecialist(){specialist()}
document.getElementById('file').addEventListener('change',e=>{if(e.target.files[0])upload(e.target.files[0])});
const drop=document.getElementById('drop');['dragenter','dragover'].forEach(x=>drop.addEventListener(x,e=>{e.preventDefault();drop.style.background='#fff4ed'}));drop.addEventListener('dragleave',()=>drop.style.background='');drop.addEventListener('drop',e=>{e.preventDefault();drop.style.background='';if(e.dataTransfer.files[0])upload(e.dataTransfer.files[0])});
async function upload(file){add(`📎 ${file.name}`,'user');const f=new FormData();f.append('file',file);f.append('message','Проанализируй загруженный файл и дай краткий вывод.');const typing=add('Анализирую файл…','bot typing');try{const r=await fetch(`/api/chat/${sid}/file`,{method:'POST',body:f});const j=await r.json();typing.remove();add(j.answer||j.detail||'Файл принят.',r.ok?'bot':'system')}catch(e){typing.remove();add('Ошибка обработки файла.','system')}}
init();
