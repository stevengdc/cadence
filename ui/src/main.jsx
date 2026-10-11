import {t,language,setLanguage} from './i18n';
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ChakraProvider, defaultSystem, Box, Button, Input, Textarea, Badge, Heading, Text, Flex } from '@chakra-ui/react';
import { Music2, Compass, ListMusic, Library, Download, CalendarDays, Workflow, Users, Settings, Radio, LogOut, ArrowUpRight, Play, Check, Clock, Heart, Search, Menu, X, Sun, Moon, Server, RefreshCw } from 'lucide-react';
import './style.css';
const api = async (path, data) => {
  const r = await fetch('/api/' + path, {
    credentials: 'same-origin',
    headers: data ? {
      'Content-Type': 'application/json'
    } : {},
    method: data ? 'POST' : 'GET',
    body: data ? JSON.stringify(data) : undefined
  });
  let d;
  try {
    d = await r.json();
  } catch {
    throw Error(t("N\xE3o foi poss\xEDvel contactar o servidor."));
  }
  if (!r.ok) {
    const e = Error(d.error || t("Pedido falhou."));
    e.status = r.status;
    throw e;
  }
  return d;
};
const NAV = [['discover', t("Descobrir"), Compass, t("M\xDASICA")], ['playlists', t("Playlists"), ListMusic], ['library', t("Biblioteca"), Library], ['redistribution', t("Redistribui\xE7\xE3o"), Check], ['downloads', t("Transfer\xEAncias"), Download, t("ATIVIDADE")], ['tasks', t("Atividade"), CalendarDays], ['automations', t("Automatiza\xE7\xF5es"), Clock], ['components', t("Componentes"), Workflow, t("ADMINISTRA\xC7\xC3O")], ['users', t("Utilizadores"), Users], ['account', t("A minha conta"), Settings]];
const labels = {
  queued: t("Por pesquisar"),
  prepared: t("Encontrada"),
  searching: t("A pesquisar"),
  downloading: t("A descarregar"),
  converting: t("A validar"),
  indexing: t("A indexar"),
  completed: t("Dispon\xEDvel"),
  review: t("Requer revis\xE3o"),
  retry: t("Nova tentativa"),
  failed: t("Falhou"),
  cancelled: t("Cancelada")
};
const date = x => x ? new Date(x * 1000).toLocaleString(language==='pt'?'pt-PT':'en-GB') : '';
function App() {
  const [user, setUser] = useState(null),
    [boot, setBoot] = useState(true),
    [section, setSection] = useState(sessionStorage.getItem('mc_section_v2') || 'discover'),
    [open, setOpen] = useState(false),
    [notice, setNotice] = useState(''),
    [busy, setBusy] = useState(false),
    [status, setStatus] = useState(null),
    [daily, setDaily] = useState(null),
    [tracks, setTracks] = useState([]),
    [jobs, setJobs] = useState(null),
    [lists, setLists] = useState([]),
    [listId, setListId] = useState(''),
    [listDetail, setListDetail] = useState(null),
    [tasks, setTasks] = useState([]),
    [automations, setAutomations] = useState([]),
    [users, setUsers] = useState([]),
    [services, setServices] = useState([]),
    [player, setPlayer] = useState(null),
    [autoplay, setAutoplay] = useState(localStorage.getItem('mc_preview_autoplay') !== 'off');
  const [deployment, setDeployment] = useState({});
  useEffect(() => {
    if (user) api('deployment').then(setDeployment).catch(() => {});
  }, [user?.id]);
  const [lane, setLane] = useState('style'),
    [day, setDay] = useState('all'),
    [filter, setFilter] = useState('pending'),
    [search, setSearch] = useState(''),
    [jobFilter, setJobFilter] = useState('all'),
    [selectedTrack, setSelectedTrack] = useState('');
  const [sharing, setSharing] = useState(null),
    [shareSelected, setShareSelected] = useState([]),
    [shareFilter, setShareFilter] = useState('all');
  const loadSharing = async () => {
    setSharing(await api('redistribution'));
    setShareSelected([]);
  };
  useEffect(() => {
    if (user?.role === 'admin' && section === 'redistribution') loadSharing().catch(e => notify(e.message));
  }, [user?.id, section]);
  const shareRows = (sharing?.files || []).filter(t => (t.artist + ' ' + t.title + ' ' + t.filename).toLocaleLowerCase().includes(search.toLocaleLowerCase())).filter(t => shareFilter === 'all' || (shareFilter === 'eligible' ? t.eligible : shareFilter === 'authorized' ? t.authorized : !t.authorized));
  const selectedShares = shareRows.filter(t => shareSelected.includes(t.id));
  const saveSharing = allowed => act(async () => {
    await api('redistribution', {
      ids: selectedShares.map(t => t.id),
      authorized: allowed
    });
    await loadSharing();
    notify(allowed ? t("Autoriza\xE7\xE3o de redistribui\xE7\xE3o guardada.") : t("Autoriza\xE7\xF5es revogadas."));
  });
  const [fileReview, setFileReview] = useState(null);
  const [libraryData, setLibraryData] = useState(null),
    [libraryBusy, setLibraryBusy] = useState(false),
    [deleteTrack, setDeleteTrack] = useState(null),
    [gridSort, setGridSort] = useState('artist'),
    [gridDir, setGridDir] = useState(1),
    [gridPage, setGridPage] = useState(0),
    [pageSize, setPageSize] = useState(25),
    [codecFilter, setCodecFilter] = useState('all');
  const [activityData, setActivityData] = useState(null),
    [activityKind, setActivityKind] = useState('all'),
    [activityOffset, setActivityOffset] = useState(0);
  const loadLibrary = async () => {
    setLibraryBusy(true);
    try {
      setLibraryData(await api('library'));
    } finally {
      setLibraryBusy(false);
    }
  };
  const loadActivity = async () => setActivityData(await api('activity?kind=' + activityKind + '&search=' + encodeURIComponent(search) + '&offset=' + activityOffset));
  useEffect(() => {
    if (user && section === 'library') loadLibrary().catch(e => notify(e.message));
  }, [user?.id, section]);
  useEffect(() => {
    if (!user || section !== 'tasks') return;
    const timeout = setTimeout(() => loadActivity().catch(e => notify(e.message)), 250);
    const timer = setInterval(() => {
      if (!document.hidden) loadActivity().catch(() => {});
    }, 15000);
    return () => {
      clearTimeout(timeout);
      clearInterval(timer);
    };
  }, [user?.id, section, activityKind, activityOffset, search]);
  useEffect(() => setGridPage(0), [search, codecFilter, pageSize]);
  const bytes = n => n >= 1073741824 ? (n / 1073741824).toFixed(2) + ' GB' : (n / 1048576).toFixed(2) + ' MB';
  const length = n => n ? Math.floor(n / 60) + ':' + String(Math.round(n % 60)).padStart(2, '0') : '—';
  const gridRows = (libraryData?.files || []).filter(t => codecFilter === 'all' || t.codec === codecFilter).filter(t => (t.artist + ' ' + t.title + ' ' + t.filename + ' ' + (t.playlists || []).map(p => p.name).join(' ')).toLocaleLowerCase().includes(search.toLocaleLowerCase())).sort((a, b) => {
    let x = a[gridSort] ?? '',
      y = b[gridSort] ?? '';
    return gridDir * (typeof x === 'number' ? x - y : String(x).localeCompare(String(y), 'pt'));
  });
  const gridPages = Math.max(1, Math.ceil(gridRows.length / pageSize));
  const safePage = Math.min(gridPage, gridPages - 1);
  const sortColumn = (key, title) => <button className="sort-column" onClick={() => {
    setGridSort(key);
    setGridDir(gridSort === key ? -gridDir : 1);
  }}>{title}{gridSort === key ? gridDir === 1 ? ' ↑' : ' ↓' : ''}</button>;
  const notify = msg => {
    setNotice(msg);
    setTimeout(() => setNotice(''), 6000);
  };
  const act = async fn => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      notify(e.message);
      if (e.status === 401) setUser(null);
    } finally {
      setBusy(false);
    }
  };
  const loadDaily = async (d = day) => setDaily(await api('daily?day=' + encodeURIComponent(d)));
  const loadJobs = async () => setJobs(await api('acquisition'));
  const loadLists = async () => {
    const d = await api('playlists');
    setLists(d);
    setListId(old => d.some(x => x.id === old) ? old : d[0]?.id || '');
  };
  const load = async u => {
    const result = await Promise.allSettled([api('status'), api('daily?day=all'), api('tracks'), api('acquisition'), api('tasks'), api('automations'), api('services')]);
    const setters = [setStatus, setDaily, setTracks, setJobs, setTasks, setAutomations, setServices];
    result.forEach((r, i) => {
      if (r.status === 'fulfilled') setters[i](r.value);else notify(r.reason.message);
    });
    await loadLists().catch(e => notify(e.message));
    if (u.role === 'admin') setUsers(await api('users'));
  };
  useEffect(() => {
    api('me').then(async u => {
      setUser(u);
      await load(u);
    }).catch(e => {
      if (e.status !== 401) notify(e.message);
    }).finally(() => setBoot(false));
  }, []);
  useEffect(() => {
    if (!user) return;
    const media = matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      document.documentElement.dataset.theme = user.theme === 'system' ? media.matches ? 'dark' : 'light' : user.theme;
      document.documentElement.classList.toggle('dark', document.documentElement.dataset.theme === 'dark');
      document.documentElement.classList.toggle('light', document.documentElement.dataset.theme === 'light');
      document.documentElement.dataset.accent = user.accent;
    };
    apply();
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [user]);
  useEffect(() => {
    if (listId) api('playlist?id=' + encodeURIComponent(listId)).then(setListDetail).catch(e => notify(e.message));else setListDetail(null);
  }, [listId]);
  useEffect(() => {
    if (!user) return;
    const timer = setInterval(() => {
      if (!document.hidden) loadJobs().catch(() => {});
    }, 30000);
    return () => clearInterval(timer);
  }, [user]);
  const go = s => {
    setSection(s);
    setSearch('');
    setOpen(false);
    sessionStorage.setItem('mc_section_v2', s);
    window.scrollTo(0, 0);
  };
  const preview = t => setPlayer({
    id: t.id || t.track_id,
    title: t.title,
    artist: t.artist,
    deezer_id: t.deezer_id,
    local_preview: t.local_preview
  });
  const deferred = t => t.deferred_until && t.deferred_until > (daily?.today || new Date().toISOString().slice(0, 10));
  const decide = async (t, decision) => act(async () => {
    if (decision === 'defer') {
      await api('defer', {
        id: t.track_id || t.id
      });
      notify(t("N\xE3o hoje. Volta a aparecer amanh\xE3, sem alterar o teu gosto."));
    } else if (t.day) {
      const result = await api('daily-decision', {
        day: t.day,
        lane: t.lane,
        id: t.track_id,
        decision
      });
      notify(decision > 0 ? result.ready ? t("Avalia\xE7\xE3o guardada. M\xFAsica na playlist.") : t("Avalia\xE7\xE3o guardada. M\xFAsica pendente na playlist.") : t("Avalia\xE7\xE3o guardada."));
    } else {
      await api('rating', {
        id: t.id,
        rating: decision
      });
      notify('O teu gosto foi atualizado.');
    }
    await loadDaily();
    setTracks(await api('tracks'));
    setStatus(await api('status'));
  });
  const TrackCard = ({
    t,
    teach = true
  }) => <article className="track-card"><div className="album"><Music2 size={24} /><span>{t.artist?.slice(0, 1)}</span></div><div className="track-copy"><strong>{t.title}</strong><p>{t.artist}</p><div className="track-meta">{t.day && <span>{t.day}</span>}{t.decision > 0 || t.rating > 0 ? <Badge colorPalette="teal">{(t.decision || t.rating) === 2 ? t("Adoro") : t("Gosto")}</Badge> : t.decision === -1 || t.rating === -1 ? <Badge colorPalette="red">{t("N\xE3o gosto")}</Badge> : deferred(t) ? <Badge colorPalette="orange">{t("N\xE3o hoje \xB7 volta amanh\xE3")}</Badge> : <Badge variant="outline">{t("Por avaliar")}</Badge>}{t.available && <span className="good">{t("Na biblioteca")}</span>}</div>{t.reason && <p className="reason">{t.reason}</p>}</div><div className="track-actions"><Button size="sm" variant="outline" onClick={() => preview(t)} disabled={!t.deezer_id && !t.local_preview}><Play size={14} />{t("Pr\xE9via")}</Button>{teach && <><Button size="sm" variant={(t.decision || t.rating) === 2 ? 'solid' : 'outline'} colorPalette="teal" aria-pressed={(t.decision || t.rating) === 2} disabled={busy} onClick={() => decide(t, 2)}><Heart size={14} />{t("Adoro")}</Button><Button size="sm" variant={(t.decision || t.rating) === 1 ? 'solid' : 'outline'} colorPalette="teal" aria-pressed={(t.decision || t.rating) === 1} disabled={busy} onClick={() => decide(t, 1)}>{t("Gosto")}</Button><Button size="sm" variant={(t.decision || t.rating) === -1 ? 'solid' : 'ghost'} aria-pressed={(t.decision || t.rating) === -1} disabled={busy} onClick={() => decide(t, -1)}>{t("N\xE3o gosto")}</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => decide(t, 'defer')}><Clock size={14} />{t("N\xE3o hoje")}</Button></>}</div></article>;
  if (boot) return <div className="loading"><Music2 /><p>{t("A abrir o teu Media Center\u2026")}</p></div>;
  if (!user) return <div className="login-layout"><div className="login-story"><div className="brand"><span className="brand-icon"><Music2 /></span>Cadence<span className="brand-small">MEDIA CENTER</span></div><span className="eyebrow">{t("A TUA COLE\xC7\xC3O. O TEU RITMO.")}</span><h1>{t("H\xE1 sempre uma")}<br />{t("pr\xF3xima favorita.")}</h1><p>{t("O teu gosto d\xE1 o rumo. Descobre, escolhe e leva as tuas playlists contigo.")}</p><div className="soundbars">{Array.from({
          length: 36
        }, (_, i) => <i key={i} style={{
          height: 20 + Math.sin(i * 0.6) ** 2 * 90
        }} />)}</div></div><Box className="login-card"><Badge colorPalette="teal">{t("O teu espa\xE7o de m\xFAsica")}</Badge><Heading size="2xl" mt="5">{t("Bem-vindo de volta")}</Heading><Text mt="2" mb="7" color="var(--muted)">{t("Entra no teu perfil para continuar.")}</Text><select aria-label="Language / Idioma" value={language} onChange={e=>setLanguage(e.target.value)}><option value="en">English</option><option value="pt">Português</option></select><form onSubmit={e => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        act(async () => {
          await api('login', Object.fromEntries(f));
          const u = await api('me');
          setUser(u);
          await load(u);
        });
      }}><label>{t("Utilizador")}<Input name="username" defaultValue="" autoComplete="username" required /></label><label>{t("Password")}<Input name="password" type="password" autoComplete="current-password" required /></label><Button type="submit" colorPalette="teal" width="full" mt="5" disabled={busy}>{t("Entrar ")}<ArrowUpRight size={17} /></Button></form>{notice && <p role="alert" className="notice-inline">{notice}</p>}<p className="login-foot">{t("Biblioteca privada \xB7 Cadence")}</p></Box></div>;
  const visibleNav = NAV.filter(n => !['users', 'redistribution'].includes(n[0]) || user.role === 'admin');
  const counts = jobs?.counts || {};
  const today = daily?.today || '';
  const proposals = (daily?.tracks || []).filter(t => t.lane === lane && (day === 'all' || t.day === day)).filter(t => filter === 'all' || filter === 'deferred' ? filter === 'all' || deferred(t) : filter === 'pending' ? !(t.decision || t.rating) && !deferred(t) : filter === 'approved' ? (t.decision || t.rating) > 0 : (t.decision || t.rating) < 0).filter(t => (t.artist + ' ' + t.title).toLowerCase().includes(search.toLowerCase()));
  return <div className={'app ' + (player ? 'has-player' : '')}>
 <aside className={'sidebar ' + (open ? 'is-open' : '')}><button className="brand" onClick={() => go('discover')}><span className="brand-icon"><Music2 /></span>Cadence</button><p className="sidebar-caption">{t("O TEU MEDIA CENTER")}</p><nav aria-label={t("Menu principal")}>{visibleNav.map(([id, title, Icon, group]) => <React.Fragment key={id}>{group && <div className="nav-group">{group}</div>}<button onClick={() => go(id)} className={'nav-item ' + (section === id ? 'selected' : '')} aria-current={section === id ? 'page' : undefined}><Icon size={19} />{title}{id === 'downloads' && (counts.downloading || 0) > 0 && <span className="nav-count">{counts.downloading}</span>}</button></React.Fragment>)}</nav><div className="sidebar-bottom"><div className="avatar">{user.name[0]}</div><div><strong>{user.name}</strong><small>{user.role === 'admin' ? t("Administrador") : t("Membro")}</small></div><button aria-label={t("Terminar sess\xE3o")} onClick={() => act(async () => {
          await api('logout', {});
          setUser(null);
          setPlayer(null);
        })}><LogOut size={18} /></button></div></aside>
 {open && <div className="scrim" onClick={() => setOpen(false)} />}
 <div className="workspace"><header className="topbar"><select aria-label="Language / Idioma" value={language} onChange={e=>setLanguage(e.target.value)}><option value="en">English</option><option value="pt">Português</option></select><button className="mobile-menu icon-button" aria-label={t("Abrir menu")} onClick={() => setOpen(!open)}><Menu /></button><span className="breadcrumb">{t("O meu espa\xE7o ")}<span>/</span> <strong>{NAV.find(n => n[0] === section)?.[1]}</strong></span><div className="topbar-right"><span className="live-dot" />{t("Biblioteca privada ")}<button className="icon-button" aria-label={t("Alternar tema")} onClick={() => act(async () => {
            await api('account', {
              theme: user.theme === 'light' ? 'dark' : 'light'
            });
            setUser(await api('me'));
          })}>{user.theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}</button></div></header>
 <main><div className="page-heading"><div><span className="eyebrow">{section === 'discover' ? t("FEITO PARA TI") : t("O TEU ESPA\xC7O, ORGANIZADO")}</span><h1>{section === 'discover' ? t("Hoje, ao teu ritmo.") : NAV.find(n => n[0] === section)?.[1]}</h1><p>{{
                discover: t("Descobre novas m\xFAsicas e ensina o teu gosto. Sem pressa, sem obriga\xE7\xE3o."),
                playlists: t("Organiza a tua cole\xE7\xE3o. As playlists acompanham-te no Emby e no Symfonium."),
                redistribution: t("Autoriza explicitamente as m\xFAsicas que podes redistribuir no Soulseek."),
                library: t("S\xF3 as m\xFAsicas descarregadas. Ficheiros, qualidade e presen\xE7a nas playlists."),
                downloads: t("Da aprova\xE7\xE3o \xE0 biblioteca. Acompanha cada etapa."),
                tasks: t("O registo das pesquisas, transfer\xEAncias e importa\xE7\xF5es do sistema."),
                automations: t("V\xEA o que corre sozinho e ajusta os hor\xE1rios."),
                components: t("Como os servi\xE7os se ligam para levar a m\xFAsica at\xE9 ti."),
                users: t("Perfis pessoais, com avalia\xE7\xF5es e playlists independentes."),
                account: t("A tua identidade, as tuas prefer\xEAncias e a apar\xEAncia da aplica\xE7\xE3o.")
              }[section]}</p></div>{section === 'discover' && <a className="external-link" href={deployment.emby_url} target="_blank" rel="noopener">{t("Abrir Emby ")}<ArrowUpRight size={16} /></a>}</div>
 {section === 'discover' && <><div className="stats-grid"><Stat title={t("Na biblioteca")} value={status?.counts.available || 0} sub={t("M\xFAsicas prontas para ouvir")} icon={Library} /><Stat title={t("O teu gosto")} value={status?.counts.rated || 0} sub={t("Avalia\xE7\xF5es que d\xE3o o rumo")} icon={Heart} /><Stat title="Em transferência" value={(counts.downloading || 0) + (counts.converting || 0)} sub={jobs?.enabled ? t("Aquisi\xE7\xE3o autom\xE1tica ativa") : 'Aquisição pausada'} icon={Download} /><Stat title={t("Espa\xE7o livre")} value={(status?.free_gb || 0) + ' GB'} sub={t("Para a cole\xE7\xE3o continuar a crescer")} icon={Server} /></div><div className="discovery-banner"><div><Badge colorPalette="teal">{t("A escolha \xE9 sempre tua")}</Badge><h2>{t("Nem todos os dias soam igual.")}</h2><p>{t("N\xE3o est\xE1s no mood? Escolhe \xABN\xE3o hoje\xBB. A m\xFAsica volta amanh\xE3 e o teu gosto fica intacto.")}</p></div><div className="banner-art"><Radio size={68} /><span className="orbit" /></div></div><div className="section-title"><div><h2>{t("Ensinar o teu gosto")}</h2><p>{t("At\xE9 10 propostas por lista, todos os dias.")}</p></div><span className="subtle">{proposals.length}{t(" m\xFAsicas nesta vista")}</span></div><div className="lane-tabs">{[['style', t("O meu estilo")], ['global', 'Tops'], ['portuguese', t("Portuguesas")]].map(([id, name]) => <button key={id} className={lane === id ? 'active' : ''} onClick={() => setLane(id)}>{name}</button>)}</div><div className="filters"><SearchInput value={search} onChange={setSearch} placeholder={t("Procurar nesta sele\xE7\xE3o")} /><Select label="Dia" value={day} onChange={setDay}><option value="all">{t("Todos os dias")}</option>{daily?.days.map(d => <option key={d}>{d}</option>)}</Select><Select label={t("Avalia\xE7\xE3o")} value={filter} onChange={setFilter}><option value="pending">{t("Por avaliar")}</option><option value="deferred">{t("N\xE3o hoje")}</option><option value="approved">{t("Aprovadas")}</option><option value="rejected">{t("N\xE3o gosto")}</option><option value="all">{t("Todas")}</option></Select></div><div className="card-stack">{proposals.map(t => <TrackCard key={t.day + t.lane + t.track_id} t={t} />)}{!proposals.length && <Empty title={t("Tudo em dia por aqui.")} text={t("Escolhe outro filtro ou volta amanh\xE3 para novas propostas.")} />}</div><details className="surface"><summary>{t("Fontes dos tops e edi\xE7\xF5es")}</summary>{daily?.charts.map(c => <p key={c.region}><a href={c.url} target="_blank" rel="noopener">{c.region.toUpperCase()} · {c.edition || t("Edi\xE7\xE3o indispon\xEDvel")}</a>{c.error && ' · ' + c.error}</p>)}</details></>}
 {section === 'redistribution' && user.role === 'admin' && <><div className="surface"><h2>{t("Autoriza\xE7\xF5es de redistribui\xE7\xE3o")}</h2><p>{t("Aprovar uma m\xFAsica para ouvir n\xE3o a autoriza para partilha. Seleciona apenas m\xFAsicas cuja redistribui\xE7\xE3o podes autorizar. S\xF3 ficheiros aprovados em MP3 a 320 kbps s\xE3o eleg\xEDveis.")}</p><p>{t("As altera\xE7\xF5es s\xE3o aplicadas ao Soulseek em at\xE9 um minuto. Revogar impede novas transfer\xEAncias; n\xE3o recupera c\xF3pias j\xE1 recebidas.")}</p></div><div className="filters"><SearchInput value={search} onChange={setSearch} placeholder={t("Procurar m\xFAsica ou artista")} /><Select label={t("Autoriza\xE7\xE3o")} value={shareFilter} onChange={v => {
              setShareFilter(v);
              setShareSelected([]);
            }}><option value="all">{t("Todas")}</option><option value="eligible">{t("Eleg\xEDveis \xB7 MP3 320 kbps")}</option><option value="authorized">{t("Autorizadas")}</option><option value="pending">{t("Sem autoriza\xE7\xE3o")}</option></Select><Button variant="outline" onClick={() => act(loadSharing)}>{t("Atualizar")}</Button></div><div className="inline-form"><span>{selectedShares.length}{t(" selecionadas")}</span><Button disabled={busy || !selectedShares.length || selectedShares.some(t => !t.eligible)} onClick={() => saveSharing(true)}>{t("Autorizar selecionadas")}</Button><Button variant="outline" disabled={busy || !selectedShares.length} onClick={() => saveSharing(false)}>{t("Revogar selecionadas")}</Button></div><div className="surface grid-surface"><div className="data-grid-scroll" tabIndex="0" aria-label={t("Tabela de autoriza\xE7\xF5es de redistribui\xE7\xE3o")}><table className="file-grid"><thead><tr><th><input type="checkbox" aria-label={t("Selecionar todas as eleg\xEDveis vis\xEDveis")} checked={!!shareRows.filter(t => t.eligible).length && shareRows.filter(t => t.eligible).every(t => shareSelected.includes(t.id))} onChange={e => setShareSelected(e.target.checked ? shareRows.filter(t => t.eligible).map(t => t.id) : [])} /></th><th>{t("M\xFAsica")}</th><th>{t("Artista")}</th><th>{t("Formato / qualidade")}</th><th>{t("Autoriza\xE7\xE3o")}</th><th>{t("\xDAltima altera\xE7\xE3o")}</th></tr></thead><tbody>{shareRows.map(t => <tr key={t.id}><td><input type="checkbox" aria-label={t("Selecionar ") + t.artist + ' · ' + t.title} checked={shareSelected.includes(t.id)} onChange={e => setShareSelected(old => e.target.checked ? [...old, t.id] : old.filter(id => id !== t.id))} /></td><td><strong>{t.title}</strong><p>{t.filename}</p></td><td>{t.artist}</td><td>{t.codec.toUpperCase()} · {t.bitrate || '—'} kbps{!t.eligible && <p>{t("N\xE3o eleg\xEDvel para autorizar")}</p>}</td><td><Badge colorPalette={t.authorized ? 'teal' : 'gray'}>{t.authorized ? 'Autorizada' : t("Sem autoriza\xE7\xE3o")}</Badge></td><td>{date(t.authorized_at) || '—'}</td></tr>)}</tbody></table></div>{!shareRows.length && <Empty title={t("Sem m\xFAsicas nesta vista.")} text={t("As m\xFAsicas descarregadas aparecem aqui.")} />}<div className="grid-pagination">{shareRows.length}{t(" m\xFAsicas \xB7 ")}{(sharing?.files || []).filter(t => t.authorized).length}{t(" autorizadas")}</div></div></>}
 {section === 'library' && <><div className="section-title"><div><h2>{libraryData?.total || 0}{t(" m\xFAsicas descarregadas")}</h2><p>{bytes(libraryData?.bytes || 0)}{t(" no total \xB7 os ficheiros s\xE3o partilhados entre os utilizadores.")}</p></div><Button variant="outline" disabled={libraryBusy} onClick={() => act(loadLibrary)}><RefreshCw size={16} />{libraryBusy ? t("A atualizar\u2026") : t("Atualizar")}</Button></div><div className="filters"><SearchInput value={search} onChange={setSearch} placeholder={t("Procurar m\xFAsica, ficheiro ou playlist")} /><Select label={t("Formato")} value={codecFilter} onChange={setCodecFilter}><option value="all">{t("Todos os formatos")}</option>{[...new Set((libraryData?.files || []).map(t => t.codec))].sort().map(c => <option key={c} value={c}>{c.toUpperCase() || 'Desconhecido'}</option>)}</Select><Select label={t("Linhas por p\xE1gina")} value={String(pageSize)} onChange={v => setPageSize(Number(v))}>{[25, 50, 100].map(n => <option key={n}>{n}</option>)}</Select></div>{libraryData && !libraryData.playlists_ready && <p role="status" className="notice-inline">{t("O Emby est\xE1 indispon\xEDvel. A contagem de playlists ser\xE1 atualizada quando voltar a responder.")}</p>}<div className="surface grid-surface"><div className="data-grid-scroll" tabIndex="0" aria-label={t("Tabela de ficheiros. Desliza horizontalmente para ver todos os detalhes.")}><table className="file-grid"><thead><tr><th aria-sort={gridSort === 'title' ? gridDir === 1 ? 'ascending' : 'descending' : 'none'}>{sortColumn('title', t("M\xFAsica / ficheiro"))}</th><th>{sortColumn('artist', t("Artista"))}</th><th>{sortColumn('codec', t("Formato"))}</th><th>{sortColumn('bitrate', t("Qualidade"))}</th><th>{t("Volume / ReplayGain")}</th><th>{sortColumn('duration', t("Dura\xE7\xE3o"))}</th><th>{sortColumn('size', t("Tamanho"))}</th><th>{sortColumn('playlist_count', t("Playlists"))}</th><th>{sortColumn('modified', t("Data do ficheiro"))}</th><th>{t("A\xE7\xF5es")}</th></tr></thead><tbody>{gridRows.slice(safePage * pageSize, (safePage + 1) * pageSize).map(t => <tr key={t.id}><td><strong>{t.title}</strong><p title={t.filename}>{t.filename}</p><small>{t.folder || 'Raiz'}</small></td><td>{t.artist}</td><td><Badge variant="outline">{t.codec.toUpperCase() || '—'}</Badge></td><td><strong>{t.bitrate ? t.bitrate + ' kbps' : '—'}</strong><p>{t.sample_rate ? t.sample_rate / 1000 + ' kHz' : ''}{t.bits ? ' · ' + t.bits + ' bit' : ''}{t.channels ? ' · ' + t.channels + t(" canais") : ''}</p>{t.metadata_error && <small>{t("Metadados indispon\xEDveis")}</small>}</td><td>{t.loudness ? <><strong>{t.loudness.lufs.toFixed(1)} LUFS</strong><p>{t.loudness.gain_db > 0 ? '+' : ''}{t.loudness.gain_db.toFixed(2)} dB · ReplayGain</p>{t.loudness.peak_limited && <small>{t("Ganho limitado para evitar picos")}</small>}</> : <span>{t("Por analisar")}</span>}</td><td>{length(t.duration)}</td><td>{bytes(t.size)}</td><td>{t.playlists ? <details><summary>{t.playlist_count} playlist{t.playlist_count === 1 ? '' : 's'}</summary>{t.playlists.map(p => <button key={p.id} className="playlist-reference" onClick={() => {
                          go('playlists');
                          setListId(p.id);
                        }}>{p.name}</button>)}</details> : 'Indisponível'}</td><td>{date(t.modified)}</td><td><div className="grid-actions"><Button size="sm" variant="outline" onClick={() => preview(t)} disabled={!t.local_preview && !t.deezer_id}><Play size={13} />{t("Pr\xE9via")}</Button>{user.role === 'admin' && <Button size="sm" colorPalette="red" variant="ghost" onClick={() => setDeleteTrack(t)}>{t("Eliminar")}</Button>}</div></td></tr>)}</tbody></table></div>{!gridRows.length && <Empty title={libraryBusy ? t("A ler os ficheiros\u2026") : t("Nenhum ficheiro nesta vista.")} text={t("A Biblioteca mostra apenas m\xFAsicas descarregadas; as sugest\xF5es ficam em Descobrir.")} />}<div className="grid-pagination"><span>{gridRows.length}{t(" resultados \xB7 p\xE1gina ")}{safePage + 1} de {gridPages}</span><div><Button size="sm" variant="outline" disabled={safePage === 0} onClick={() => setGridPage(safePage - 1)}>{t("Anterior")}</Button><Button size="sm" variant="outline" disabled={safePage + 1 >= gridPages} onClick={() => setGridPage(safePage + 1)}>{t("Seguinte")}</Button></div></div></div>{user.role === 'admin' && <details className="surface"><summary>{t("Reciclagem \xB7 ")}{libraryData?.trash.length || 0}{t(" m\xFAsicas")}</summary><p>{t("Os ficheiros removidos ficam guardados para recupera\xE7\xE3o. As avalia\xE7\xF5es s\xE3o preservadas; a aquisi\xE7\xE3o autom\xE1tica fica cancelada.")}</p>{libraryData?.trash.map(t => <div className="list-row" key={t.id}><div><strong>{t.artist} · {t.title}</strong><p>{date(t.created)}</p></div><Button size="sm" disabled={busy} onClick={() => act(async () => {
                await api('library-restore', {
                  id: t.id
                });
                await loadLibrary();
                notify(t("Ficheiro restaurado. As playlists ser\xE3o atualizadas ap\xF3s reindexa\xE7\xE3o no Emby."));
              })}>{t("Restaurar")}</Button></div>)}</details>}</>}
 {section === 'playlists' && <><div className="surface"><form className="inline-form" onSubmit={e => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              const form = e.currentTarget;
              act(async () => {
                const d = await api('playlist-create', {
                  name: f.get('name')
                });
                form.reset();
                await loadLists();
                setListId(d.id);
                notify(t("Playlist criada."));
              });
            }}><Input name="name" placeholder={t("Nome da nova playlist")} aria-label={t("Nome da nova playlist")} required maxLength={100} /><Button colorPalette="teal" type="submit" disabled={busy}>{t("Criar playlist")}</Button></form></div><div className="playlist-layout"><div className="playlist-list">{lists.map(l => <button key={l.id} className={'playlist-tile ' + (listId === l.id ? 'active' : '')} onClick={() => setListId(l.id)}><ListMusic /><span>{l.name}</span><ArrowUpRight size={16} /></button>)}{!lists.length && <Empty title={t("A tua primeira playlist")} text={t("Cria uma lista para come\xE7ar a organizar as m\xFAsicas.")} />}</div><div className="surface"><h2>{lists.find(l => l.id === listId)?.name || t("Escolhe uma playlist")}</h2>{listId && <><p className="subtle">{listDetail?.ready.length || 0} disponíveis · {listDetail?.pending.length || 0}{t(" a aguardar ficheiro")}</p><SearchInput value={search} onChange={setSearch} placeholder={t("Procurar m\xFAsica para adicionar")} /><div className="inline-form"><select aria-label={t("M\xFAsica para adicionar")} value={selectedTrack} onChange={e => setSelectedTrack(e.target.value)}><option value="">{t("Selecionar m\xFAsica\u2026")}</option>{tracks.filter(t => (t.artist + ' ' + t.title).toLowerCase().includes(search.toLowerCase())).map(t => <option key={t.id} value={t.id}>{t.artist} · {t.title}{!t.available ? t(" \xB7 sem ficheiro") : ''}</option>)}</select><Button disabled={busy || !selectedTrack} onClick={() => act(async () => {
                    const r = await api('playlist-add', {
                      playlist_id: listId,
                      track_id: Number(selectedTrack)
                    });
                    setListDetail(await api('playlist?id=' + listId));
                    notify(r.ready ? 'Adicionada.' : t("Adicionada \xB7 aguarda ficheiro."));
                  })}>{t("Adicionar")}</Button></div>{[...(listDetail?.ready || []), ...(listDetail?.pending || [])].map((t, i) => <div className="list-row" key={t.entry_id || t.id || i}><div><strong>{t.title}</strong><p>{t.artist}{!t.ready ? t(" \xB7 aguarda ficheiro") : ''}</p></div><Button size="sm" variant="ghost" disabled={busy} onClick={() => act(async () => {
                    await api('playlist-remove', {
                      playlist_id: listId,
                      ...(t.entry_id ? {
                        entry_id: t.entry_id
                      } : {
                        track_id: t.id
                      })
                    });
                    setListDetail(await api('playlist?id=' + listId));
                  })}>{t("Remover")}</Button></div>)}</>}</div></div><div className="surface"><h3>{t("As tuas playlists, no telem\xF3vel")}</h3><p>{t("No Symfonium, ativa a importa\xE7\xE3o autom\xE1tica de playlists do fornecedor Emby e sincroniza. As r\xE1dios de m\xFAsicas e playlists locais continuam dispon\xEDveis.")}</p></div></>}
 {section === 'downloads' && <><div className="stats-grid"><Stat title={t("Conclu\xEDdas")} value={counts.completed || 0} sub={t("Dispon\xEDveis na biblioteca")} icon={Check} /><Stat title={t("Por efetuar")} value={(counts.queued || 0) + (counts.prepared || 0) + (counts.retry || 0)} sub={t("Fila de m\xFAsicas aprovadas")} icon={Clock} /><Stat title={t("Em curso")} value={(counts.downloading || 0) + (counts.searching || 0) + (counts.converting || 0) + (counts.indexing || 0)} sub={t("Pesquisa, transfer\xEAncia e importa\xE7\xE3o")} icon={Download} /><Stat title={t("Requerem aten\xE7\xE3o")} value={(counts.review || 0) + (counts.failed || 0)} sub={t("Qualidade ou correspond\xEAncia")} icon={Search} /></div><div className="surface"><div className="section-title"><div><h2>{jobs?.enabled ? t("Aquisi\xE7\xE3o autom\xE1tica ativa") : t("Novas aquisi\xE7\xF5es pausadas")}</h2><p>{t("Pesquisa a lista inteira. Repete falhadas ap\xF3s ")}{status?.policy.retry_minutes || 60}{t(" minutos. ")}{jobs?.policy.prefer_lossless ? t("Prefer\xEAncia FLAC \u2192 MP3 320 normalizado. As substitui\xE7\xF5es da biblioteca exigem FLAC.") : t("Qualidade m\xEDnima: 256 kbps; prefer\xEAncia 320 kbps.")}</p></div>{user.role === 'admin' && <Button variant="outline" disabled={busy} onClick={() => act(async () => {
                await api('acquisition-control', {
                  action: jobs?.enabled ? 'pause' : 'resume'
                });
                await loadJobs();
              })}>{jobs?.enabled ? t("Pausar") : t("Retomar")}</Button>}</div><div className="filters"><SearchInput value={search} onChange={setSearch} placeholder={t("Procurar nas transfer\xEAncias")} /><Select label={t("Estado")} value={jobFilter} onChange={setJobFilter}><option value="all">{t("Todos os estados")}</option><option value="todo">{t("Por efetuar")}</option><option value="active">{t("Em curso")}</option><option value="completed">{t("Conclu\xEDdos")}</option><option value="attention">{t("Requerem aten\xE7\xE3o")}</option>{Object.entries(labels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select><Button variant="ghost" onClick={() => act(loadJobs)}><RefreshCw size={16} />{t("Atualizar")}</Button></div><div className="download-table"><div className="download-head"><span>{t("M\xFAsica")}</span><span>{t("Estado / qualidade")}</span><span>{t("Atividade / pr\xF3xima pesquisa")}</span><span /></div>{(jobs?.jobs || []).filter(t => (t.artist + ' ' + t.title).toLowerCase().includes(search.toLowerCase())).filter(t => jobFilter === 'all' || jobFilter === t.state || jobFilter === 'todo' && ['queued', 'prepared', 'retry'].includes(t.state) || jobFilter === 'active' && ['searching', 'downloading', 'converting', 'indexing'].includes(t.state) || jobFilter === 'attention' && ['review', 'failed'].includes(t.state)).map(t => <div className="download-row" key={t.id}><div><strong>{t.title}</strong><p>{t.artist}</p></div><div><Badge colorPalette={t.state === 'completed' ? 'teal' : t.state === 'review' ? 'orange' : 'gray'}>{labels[t.state] || t.state}</Badge>{t.upgrade === 1 && <p><strong>{t("FLAC \u2192 MP3 320 normalizado")}</strong></p>}<p>{t.upgrade === 1 ? t.detail : t.quality || t.detail}</p>{t.state === 'downloading' && <progress value={t.progress} max="100" aria-label={t("Progresso de ") + t.title} />}</div><div className="subtle">{['completed', 'cancelled', 'review', 'failed'].includes(t.state) ? date(t.updated) : t.next_at ? date(t.next_at) : t("Na pr\xF3xima passagem")}</div><div>{user.role === 'admin' && t.state === 'review' && <Button size="sm" colorPalette="teal" disabled={busy} onClick={() => act(async () => {
                    setFileReview(await api('review?id=' + t.id));
                  })}><Play size={14} />{t("Ouvir e rever")}</Button>}{user.role === 'admin' && ['queued', 'prepared', 'retry', 'review', 'failed'].includes(t.state) && <Button size="sm" variant="outline" disabled={busy || !!t.manual_requested} onClick={() => act(async () => {
                    await api('acquisition-control', {
                      action: 'search',
                      id: t.id
                    });
                    await loadJobs();
                    notify(t("Pesquisa priorit\xE1ria pedida."));
                  })}>{t.manual_requested ? t("Pesquisa pedida") : t("Pesquisar agora")}</Button>}</div></div>)}</div></div></>}
 {section === 'tasks' && <><div className="filters"><SearchInput value={search} onChange={v => {
              setSearch(v);
              setActivityOffset(0);
            }} placeholder={t("Procurar m\xFAsica ou mensagem no registo")} /><Select label={t("Tipo de atividade")} value={activityKind} onChange={v => {
              setActivityKind(v);
              setActivityOffset(0);
            }}><option value="all">{t("Toda a atividade")}</option><option value="search">{t("Pesquisas")}</option><option value="download">{t("Transfer\xEAncias")}</option><option value="import">{t("Valida\xE7\xE3o e importa\xE7\xE3o")}</option><option value="library">{t("Altera\xE7\xF5es na biblioteca")}</option></Select><Button variant="outline" onClick={() => act(loadActivity)}><RefreshCw size={16} />{t("Atualizar")}</Button></div><p className="subtle">{t("Atualiza a cada 15 segundos. O hist\xF3rico anterior inclui as tentativas guardadas e o \xFAltimo estado conhecido; o registo detalhado come\xE7a agora.")}</p><div className="surface activity-log"><div className="activity-log-head"><span>{t("Data / hora")}</span><span>{t("Atividade")}</span><span>{t("M\xFAsica e detalhes")}</span></div>{activityData?.entries.map(e => <article className="activity-log-row" key={e.id}><time>{date(e.created)}</time><div><Badge colorPalette={e.state === 'completed' ? 'teal' : ['review', 'failed'].includes(e.state) ? 'orange' : 'gray'}>{{
                    search: 'Pesquisa',
                    download: t("Transfer\xEAncia"),
                    import: t("Importa\xE7\xE3o"),
                    library: t("Biblioteca")
                  }[e.kind] || e.kind}</Badge><p>{labels[e.state] || {
                    started: t("Tentativa iniciada"),
                    confirmed: t("Confirmada na audi\xE7\xE3o"),
                    rejected: t("Rejeitada na audi\xE7\xE3o"),
                    removed: t("Removida"),
                    restored: t("Restaurada"),
                    loudness: t("ReplayGain calculado")
                  }[e.state] || e.state}</p></div><div><strong>{e.artist && e.title ? e.artist + ' · ' + e.title : 'Sistema'}</strong><p>{e.detail}</p></div></article>)}{!activityData?.entries.length && <Empty title={t("Sem registos nesta vista.")} text={t("As pr\xF3ximas pesquisas, transfer\xEAncias e importa\xE7\xF5es aparecem aqui.")} />}<div className="grid-pagination"><span>{activityData?.total || 0}{t(" registos \xB7 p\xE1gina ")}{Math.floor(activityOffset / 50) + 1}</span><div><Button size="sm" variant="outline" disabled={activityOffset === 0} onClick={() => setActivityOffset(Math.max(0, activityOffset - 50))}>{t("Anterior")}</Button><Button size="sm" variant="outline" disabled={activityOffset + 50 >= (activityData?.total || 0)} onClick={() => setActivityOffset(activityOffset + 50)}>{t("Seguinte")}</Button></div></div></div></>}
 {section === 'automations' && <><div className="surface info-box"><Clock /><p>{t("Estes hor\xE1rios controlam os servi\xE7os reais do Media Center. As altera\xE7\xF5es s\xE3o aplicadas em at\xE9 um minuto. O intervalo de repeti\xE7\xE3o por m\xFAsica \xE9 independente da frequ\xEAncia com que a fila \xE9 percorrida.")}</p></div><div className="automation-grid">{automations.map(a => <Automation key={a.id} item={a} admin={user.role === 'admin'} save={data => act(async () => {
              const r = await api('automations', data);
              setAutomations(await api('automations'));
              notify(r.message);
            })} />)}</div>{status && <div className="surface"><h2>{t("Regras da aquisi\xE7\xE3o")}</h2><form onSubmit={e => {
              e.preventDefault();
              const data = Object.fromEntries(new FormData(e.currentTarget));
              Object.keys(data).forEach(k => data[k] = Number(data[k]));
              act(async () => {
                await api('policy', data);
                setStatus(await api('status'));
                notify(t("Regras atualizadas."));
              });
            }} className="settings-grid">{[['retry_minutes', t("Repetir cada m\xFAsica (min)"), 15, 1440], ['concurrency', t("Transfer\xEAncias simult\xE2neas"), 1, 5], ['reserve_gb', t("Reserva de disco (GB)"), 20, 400], ['exploration_percent', t("Explora\xE7\xE3o do gosto (%)"), 0, 50]].map(([key, name, min, max]) => <label key={key}>{name}<Input type="number" name={key} min={min} max={max} defaultValue={status.policy[key]} disabled={user.role !== 'admin'} /></label>)}{user.role === 'admin' && <Button colorPalette="teal" type="submit" disabled={busy}>{t("Guardar regras")}</Button>}</form></div>}</>}
 {section === 'components' && <><div className="component-services">{services.map(s => <div className="surface" key={s.name}><span className={'live-dot ' + (!s.online ? 'offline' : '')} /><strong>{s.name}</strong><Badge colorPalette={s.online ? 'teal' : 'orange'}>{s.online ? 'Online' : 'Indisponível'}</Badge></div>)}</div><div className="surface"><h2>{t("Da descoberta \xE0 tua cole\xE7\xE3o")}</h2><p>{t("As setas mostram o caminho das propostas, aprova\xE7\xF5es, ficheiros e playlists.")}</p><div className="flow-diagram" role="img" aria-label="Catálogos e tops alimentam o painel. O utilizador aprova. A fila pesquisa no Soulseek, valida e importa no Emby. Emby fornece música e playlists ao Symfonium."><div className="flow-row"><Flow icon={Compass} title={t("Cat\xE1logos & tops")} text="Deezer · Mundial · UK · Portugal" /><span className="flow-arrow">→</span><Flow icon={Music2} title={t("Cad\xEAncia")} text={t("Gosto por utilizador \xB7 propostas")} /><span className="flow-arrow">→</span><Flow icon={Check} title={t("A tua aprova\xE7\xE3o")} text={t("Gosto / Adoro \u2192 playlist")} /></div><span className="flow-down">↓</span><div className="flow-row reverse-mobile"><Flow icon={Radio} title="Emby → Symfonium" text={t("M\xFAsica \xB7 playlists \xB7 r\xE1dios")} /><span className="flow-arrow">←</span><Flow icon={Download} title={t("Valida\xE7\xE3o & biblioteca")} text={t("256 kbps m\xEDnimo \xB7 MP3 320 preferido")} /><span className="flow-arrow">←</span><Flow icon={Search} title="Soulseek / slskd" text={t("Pesquisa independente dos downloads")} /></div></div><div className="diagram-support"><span>{t("Acesso remoto \u2192 configura\xE7\xE3o do administrador")}</span><span>{t("Docker Compose \u2192 gest\xE3o dos containers")}</span><span>{t("Backup local \u2192 perfil \xB7 Backup externo \u2192 pendente")}</span></div></div><div className="service-links">{[[t("Emby \xB7 entrar"), deployment.emby_url], [t("Soulseek \xB7 pesquisa manual"), deployment.source_url]].filter(([, url]) => url).map(([n, url]) => <a key={n} className="surface external-link" href={url} target="_blank" rel="noopener">{n}<ArrowUpRight size={16} /></a>)}</div><details className="surface"><summary>{t("O Emby fica no log\xF3tipo?")}</summary><p>{t("Abre a liga\xE7\xE3o \xABEmby \xB7 entrar\xBB. Se ficar preso, testa numa janela privada. Se funcionar, apaga os dados do site do Emby no navegador e volta a entrar. Isto limpa a sess\xE3o do navegador; mant\xE9m a biblioteca e o perfil do servidor.")}</p></details></>}
 {section === 'users' && user.role === 'admin' && <><div className="surface"><h2>{t("Adicionar utilizador")}</h2><p>{t("Cria uma conta pessoal na aplica\xE7\xE3o e no Emby. O gosto, as decis\xF5es e as playlists s\xE3o separados. A biblioteca de ficheiros \xE9 partilhada.")}</p><form className="settings-grid" onSubmit={e => {
              e.preventDefault();
              const form = e.currentTarget;
              const data = Object.fromEntries(new FormData(form));
              act(async () => {
                await api('user-create', data);
                setUsers(await api('users'));
                form.reset();
                notify(t("Conta criada na aplica\xE7\xE3o e no Emby."));
              });
            }}><label>{t("Utilizador")}<Input name="username" pattern="[A-Za-z0-9_.-]{3,40}" required autoComplete="off" /></label><label>{t("Nome")}<Input name="name" required maxLength={80} /></label><label>{t("Password inicial")}<Input name="password" type="password" minLength={8} required autoComplete="new-password" /></label><Button colorPalette="teal" type="submit" disabled={busy}>{t("Criar conta")}</Button></form></div><div className="surface">{users.map(u => <div className="list-row" key={u.id}><div className="user-name"><span className="avatar">{u.name[0]}</span><div><strong>{u.name}</strong><p>@{u.username} · {u.emby_id ? t("Emby associado") : t("Sem liga\xE7\xE3o Emby")}</p></div></div><div className="inline-form"><Badge colorPalette={u.active ? 'teal' : 'gray'}>{u.active ? t("Ativo") : t("Desativado")}</Badge><select disabled={u.id === 1 || busy} aria-label={t("Permiss\xE3o de ") + u.name} value={u.role} onChange={e => act(async () => {
                  await api('account', {
                    id: u.id,
                    role: e.target.value
                  });
                  setUsers(await api('users'));
                })}><option value="admin">{t("Administrador")}</option><option value="member">{t("Membro")}</option></select>{u.id !== 1 && <Button variant="outline" size="sm" disabled={busy} onClick={() => act(async () => {
                  await api('account', {
                    id: u.id,
                    active: u.active ? 0 : 1
                  });
                  setUsers(await api('users'));
                })}>{u.active ? t("Desativar") : t("Ativar")}</Button>}</div></div>)}</div></>}
 {section === 'account' && <><div className="account-grid"><div className="surface"><h2>{t("O teu perfil")}</h2><form onSubmit={e => {
                e.preventDefault();
                const data = Object.fromEntries(new FormData(e.currentTarget));
                act(async () => {
                  await api('account', data);
                  setUser(await api('me'));
                  notify(t("Perfil atualizado."));
                });
              }}><label>{t("Utilizador")}<Input value={user.username} readOnly /></label><label>{t("Nome")}<Input name="name" defaultValue={user.name} required maxLength={80} /></label><Button mt="4" type="submit" colorPalette="teal" disabled={busy}>{t("Guardar perfil")}</Button></form></div><div className="surface"><h2>{t("Apar\xEAncia")}</h2><p>{t("Estas escolhas acompanham a tua conta nos outros dispositivos.")}</p><label>{t("Tema")}<select aria-label={t("Tema da interface")} value={user.theme} onChange={e => act(async () => {
                  await api('account', {
                    theme: e.target.value
                  });
                  setUser(await api('me'));
                })}><option value="dark">{t("Escuro")}</option><option value="light">{t("Claro")}</option><option value="system">{t("Seguir o dispositivo")}</option></select></label><label>{t("Cor de destaque")}<select aria-label={t("Cor de destaque")} value={user.accent} onChange={e => act(async () => {
                  await api('account', {
                    accent: e.target.value
                  });
                  setUser(await api('me'));
                })}><option value="teal">{t("Verde \xE1gua")}</option><option value="blue">{t("Azul")}</option><option value="purple">{t("Violeta")}</option><option value="orange">{t("Laranja")}</option></select></label><label className="checkbox"><input type="checkbox" checked={autoplay} onChange={e => {
                  setAutoplay(e.target.checked);
                  localStorage.setItem('mc_preview_autoplay', e.target.checked ? 'on' : 'off');
                }} />{t("Reproduzir pr\xE9vias automaticamente")}</label><p className="subtle">{t("O navegador pode exigir um toque em Play.")}</p></div></div><div className="surface"><h2>{t("Prefer\xEAncias musicais")}</h2><form onSubmit={e => {
              e.preventDefault();
              const d = Object.fromEntries(new FormData(e.currentTarget));
              act(async () => {
                await api('preferences', d);
                notify(t("Prefer\xEAncias guardadas."));
              });
            }}><Textarea key={user.id} name="text" defaultValue={status?.preferences || ''} maxLength={5000} placeholder={t("O que procuras na tua m\xFAsica?")} aria-label={t("Prefer\xEAncias musicais")} /><Button mt="4" type="submit" disabled={busy}>{t("Guardar prefer\xEAncias")}</Button></form></div><div className="surface"><h2>{t("Alterar password")}</h2><p>{t("A password desta aplica\xE7\xE3o \xE9 gerida aqui. A password do Emby \xE9 gerida no perfil Emby.")}</p><form className="settings-grid" onSubmit={e => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              if (f.get('password') !== f.get('confirm')) return notify(t("As passwords n\xE3o coincidem."));
              act(async () => {
                await api('account', {
                  password: f.get('password'),
                  current_password: f.get('current_password')
                });
                setUser(null);
                notify(t("Password alterada. Entra novamente."));
              });
            }}><label>{t("Password atual")}<Input name="current_password" type="password" autoComplete="current-password" required /></label><label>{t("Nova password")}<Input name="password" type="password" minLength={8} autoComplete="new-password" required /></label><label>{t("Confirmar password")}<Input name="confirm" type="password" minLength={8} autoComplete="new-password" required /></label><Button type="submit" disabled={busy}>{t("Alterar password")}</Button></form></div></>}
 </main><footer>Cadence <span>·</span>{t(" A tua m\xFAsica, ao teu ritmo.")}</footer></div>
 {fileReview && <div className="modal-backdrop"><div className="confirm-dialog file-review" role="dialog" aria-modal="true" aria-labelledby="review-heading"><h2 id="review-heading">{t("Ouvir e rever o ficheiro")}</h2><strong>{fileReview.artist} · {fileReview.title}</strong><p>{t("Esta audi\xE7\xE3o usa o ficheiro descarregado, n\xE3o a pr\xE9via do cat\xE1logo.")}</p><audio key={fileReview.fingerprint} controls autoPlay src={'/api/review-audio/' + fileReview.id} style={{
          width: '100%'
        }} /><p>{fileReview.codec.toUpperCase()} · {fileReview.bitrate}{t(" kbps \xB7 ficheiro ")}{length(fileReview.duration)}{fileReview.expected_duration ? t(" \xB7 cat\xE1logo ") + length(fileReview.expected_duration) : ''}</p><div className="review-facts"><p>{t("Artista no ficheiro: ")}<strong>{fileReview.file_artist || t("N\xE3o preenchido")}</strong><br />{t("T\xEDtulo no ficheiro: ")}<strong>{fileReview.file_title || t("N\xE3o preenchido")}</strong></p><p>{fileReview.reason}</p></div><p>{t("Confirma apenas se ouviste e \xE9 a grava\xE7\xE3o que queres guardar. A aprova\xE7\xE3o corrige os metadados e aceita a dura\xE7\xE3o deste ficheiro; a qualidade m\xEDnima continua obrigat\xF3ria.")}</p>{fileReview.quality_error && <p role="alert" className="notice-inline">{fileReview.quality_error}</p>}<div className="inline-form"><Button variant="ghost" disabled={busy} onClick={() => setFileReview(null)}>{t("Fechar")}</Button><Button colorPalette="red" variant="outline" disabled={busy} onClick={() => act(async () => {
            await api('review-control', {
              id: fileReview.id,
              action: 'reject',
              fingerprint: fileReview.fingerprint
            });
            setFileReview(null);
            await loadJobs();
            notify(t("Ficheiro rejeitado. O sistema vai procurar outra fonte."));
          })}>{t("Rejeitar ficheiro")}</Button><Button colorPalette="teal" disabled={busy || !fileReview.can_approve} onClick={() => act(async () => {
            await api('review-control', {
              id: fileReview.id,
              action: 'approve',
              fingerprint: fileReview.fingerprint
            });
            setFileReview(null);
            await loadJobs();
            notify(t("Ficheiro confirmado. Aguarda importa\xE7\xE3o para o Emby e as playlists."));
          })}>{t("\xC9 esta m\xFAsica \xB7 aprovar")}</Button></div></div></div>}
 {deleteTrack && <div className="modal-backdrop"><div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="remove-heading"><h2 id="remove-heading">{t("Eliminar da biblioteca?")}</h2><strong>{deleteTrack.artist} · {deleteTrack.title}</strong><p>{deleteTrack.filename} · {bytes(deleteTrack.size)}</p><p>{t("O ficheiro ser\xE1 retirado da biblioteca partilhada e das ")}{deleteTrack.playlist_count ?? 'suas'}{t(" playlists. A aquisi\xE7\xE3o pendente ser\xE1 cancelada. Poder\xE1s recuper\xE1-lo na Reciclagem.")}</p><div className="inline-form"><Button variant="outline" disabled={busy} onClick={() => setDeleteTrack(null)}>{t("Cancelar")}</Button><Button colorPalette="red" disabled={busy} onClick={() => act(async () => {
            await api('library-remove', {
              id: deleteTrack.id
            });
            setDeleteTrack(null);
            await loadLibrary();
            setStatus(await api('status'));
            await loadJobs();
            notify(t("Removida da biblioteca e guardada na Reciclagem."));
          })}>{t("Eliminar ficheiro")}</Button></div></div></div>}
 {notice && <div className="toast" role="status"><Check size={18} />{notice}<button aria-label={t("Fechar aviso")} onClick={() => setNotice('')}><X size={16} /></button></div>}
 {player && <div className="player"><div className="player-title"><Music2 /><div><strong>{player.title}</strong><p>{player.artist} · prévia</p></div><button className="icon-button" aria-label={t("Fechar pr\xE9via")} onClick={() => setPlayer(null)}><X /></button></div>{player.local_preview ? <audio key={player.id} src={'/api/sample/' + player.id} controls autoPlay={autoplay} /> : <iframe key={player.id} title={t("Pr\xE9via de ") + player.title} src={'https://widget.deezer.com/widget/dark/track/' + player.deezer_id + '?autoplay=' + (autoplay ? '1' : '0')} allow="autoplay; encrypted-media" />}</div>}
 </div>;
}
function Stat({
  title,
  value,
  sub,
  icon: Icon
}) {
  return <div className="stat"><div><span>{title}</span><Icon size={18} /></div><strong>{value}</strong><p>{sub}</p></div>;
}
function Empty({
  title,
  text
}) {
  return <div className="empty"><Check size={30} /><h3>{title}</h3><p>{text}</p></div>;
}
function SearchInput({
  value,
  onChange,
  placeholder
}) {
  return <div className="search-input"><Search size={17} /><Input value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder} /></div>;
}
function Select({
  label,
  value,
  onChange,
  children
}) {
  return <label className="filter-select"><span>{label}</span><select aria-label={label} value={value} onChange={e => onChange(e.target.value)}>{children}</select></label>;
}
function Flow({
  icon: Icon,
  title,
  text
}) {
  return <div className="flow-node"><Icon /><strong>{title}</strong><span>{text}</span></div>;
}
function Automation({
  item: a,
  admin,
  save
}) {
  const [enabled, setEnabled] = useState(a.enabled),
    [value, setValue] = useState(a.kind === 'calendar' ? a.time : a.seconds);
  return <div className="surface automation"><div className="section-title"><span className="automation-icon"><Clock /></span><Badge colorPalette={a.runtime?.ActiveState === 'active' ? 'teal' : 'gray'}>{a.runtime?.ActiveState === 'active' ? 'Ativa' : 'Parada'}</Badge></div><h2>{a.name}</h2><p>{a.description}</p><form onSubmit={e => {
      e.preventDefault();
      save({
        id: a.id,
        enabled,
        ...(a.kind === 'calendar' ? {
          time: value
        } : {
          seconds: Number(value)
        })
      });
    }}><label>{a.kind === 'calendar' ? t("Hora \xB7 Lisboa") : t("Intervalo entre execu\xE7\xF5es (segundos)")}<Input type={a.kind === 'calendar' ? 'time' : 'number'} value={value} min={5} max={3600} disabled={!admin} onChange={e => setValue(e.target.value)} required /></label><label className="checkbox"><input type="checkbox" checked={enabled} disabled={!admin} onChange={e => setEnabled(e.target.checked)} />{t("Automatiza\xE7\xE3o ativa")}</label>{admin && <Button variant="outline" type="submit">{t("Guardar hor\xE1rio")}</Button>}</form><p className="subtle">{t("\xDAltima execu\xE7\xE3o: ")}{a.runtime?.LastTriggerUSec || t("Ainda sem registo")}</p><p className="subtle">{t("Pr\xF3xima: ")}{a.runtime?.NextElapseUSecRealtime || t("Conforme intervalo")}</p></div>;
}
createRoot(document.getElementById('root')).render(<ChakraProvider value={defaultSystem}><App /></ChakraProvider>);