# Prenotazioni laboratori scolastici

App da browser per i cinque laboratori della scuola, con SQLite gratuito su disco, registrazione autonoma e amministrazione. Richiede Python 3.12 o successivo e le dipendenze indicate in `requirements.txt` (ReportLab e Pillow per PDF e immagini). Nessun servizio Google o servizio email necessario.

## Primo avvio

```sh
cd /workspace/APP-LABORATORI-SCUOLA
python3 -m pip install --user -r requirements.txt
python3 app.py
```

Alla prima apertura compare **Benvenuto, Rosario**: nome Rosario Calabrese ed email rosariocalabrese80@gmail.com sono già compilati. Scegli la password e ripetila; puoi mostrarla o nasconderla. Il minimo è **6 caratteri**, senza obblighi di maiuscole, numeri, simboli o combinazioni. Il limite massimo tecnico è 256 caratteri. La stessa regola vale per registrazioni, creazione account, modifica e reset password.

Per proteggere la sola configurazione iniziale, il server genera un codice monouso nel file locale `data/laboratori.setup-token` (con `LAB_DB` personalizzato, stessa posizione del database e suffisso `.setup-token`). Apri il file sul server e incolla il codice nel campo del modulo: non inserirlo in chat o nel repository. Il codice non è la password. Non è disponibile attraverso le API o la pagina pubblica e viene eliminato dopo la configurazione. È richiesto solo una volta; serve a impedire che un visitatore si nomini primo amministratore. Le richieste concorrenti non possono creare due primi amministratori. Dopo il completamento il modulo iniziale si chiude e non può essere riutilizzato.

Non sono presenti credenziali predefinite e nessuna password del titolare è stata impostata automaticamente. In alternativa il responsabile può creare il primo amministratore dal terminale con `python3 app.py create-admin`, fornendo email, nome e password nascosta con conferma. Gli altri amministratori si gestiscono poi dal pannello.

Il server di sviluppo ascolta in locale sulla porta 8000. Configurabili `HOST`, `PORT` e `LAB_DB` (default `data/laboratori.sqlite3`). Riavviare il processo nelle nuove sessioni. Per uso online occorrono hosting con disco persistente, server di produzione dietro HTTPS e `COOKIE_SECURE=1`. Il deployment online non è configurato; la gratuità di SQLite non garantisce hosting gratuito permanente.

## Registrazione docenti

Il docente sceglie nome e cognome, **qualsiasi email valida, anche personale**, e la propria password, con conferma. L’indirizzo viene normalizzato in minuscolo e deve essere univoco. Non c’è accesso Google, non c’è restrizione al dominio della scuola, non vengono inviate email e non viene verificato il possesso della casella.

Ogni nuova iscrizione è `In attesa`: non può accedere all’agenda né prenotare. L’amministratore confronta i dati con gli elenchi cartacei e approva oppure esclude/elimina l’iscritto. Il nome su un elenco, da solo, non dimostra l’identità di chi si registra: se necessario il responsabile conferma di persona con il collega prima di approvare. Chi si registra non può assegnarsi il ruolo amministratore o l’approvazione, nemmeno modificando la richiesta HTTP.

## Pannello amministrativo

- Ricerca iscritti per nome o email, visualizzazione di ruolo e stato.
- Approvazione, esclusione immediata e riattivazione degli iscritti. L’esclusione revoca tutte le sessioni, conserva le prenotazioni per la revisione e blocca nuovi accessi.
- Eliminazione definitiva di un account e delle sue prenotazioni, con conferma nell’interfaccia.
- Creazione di docenti o amministratori attivi con email, nome e password iniziale; promozione e retrocessione degli utenti. Almeno un amministratore deve rimanere attivo.
- Reimpostazione password con revoca delle sessioni. Nessuno può leggere le password esistenti. Comunicare una password iniziale o reimpostata individualmente tramite un canale riservato; l’utente può cambiarla dopo l’accesso.
- Creazione, modifica e annullamento delle prenotazioni di qualsiasi docente. Le nuove prenotazioni possono essere intestate a un utente attivo. Le regole scolastiche e il blocco delle sovrapposizioni valgono anche per gli amministratori.
- Aggiunta e rinomina laboratori, disattivazione e riattivazione. La disattivazione impedisce nuove prenotazioni e conserva le precedenti per la gestione amministrativa.

Le autorizzazioni sono controllate anche dal server. I docenti attivi vedono l’agenda ma possono modificare o annullare soltanto le proprie prenotazioni. Possono cambiare password con verifica di quella attuale; tutte le sessioni terminano dopo il cambio. Per password dimenticata ci si rivolge all’amministratore, senza recupero automatico via email.

## Laboratori e regole

Catalogo iniziale: Informatica aula 133; STEM/Coding aula 132; Arte aula 131; Informatica carrello mobile n. 1; Informatica carrello mobile n. 2. Il catalogo viene inizializzato una volta: le modifiche amministrative sono conservate ai successivi avvii.

Prenotazioni di un’ora intera, lunedì–venerdì, nelle fasce 08–09, 09–10, 10–11, 11–12, 12–13, 13–14. Il modulo permette di spuntare più fasce orarie dello stesso giorno, anche non consecutive. Un solo salvataggio crea una prenotazione distinta per ogni ora. Le ore già occupate sono disabilitate; il server ricontrolla la disponibilità al salvataggio e, in caso di conflitto su una qualsiasi ora, non salva nessuna delle ore selezionate. La modifica amministrativa riguarda una prenotazione alla volta. Sono bloccate frazioni, sovrapposizioni e fine settimana; festività e chiusure straordinarie si configurano nel calendario delle chiusure amministrativo.

La data è quella italiana (`Europe/Rome`). Si può prenotare da oggi fino allo stesso giorno del mese successivo incluso. Se quel giorno non esiste si usa l’ultimo del mese. Non si inseriscono prenotazioni retroattive.

Le prenotazioni antecedenti allo stesso giorno del mese precedente vengono eliminate: il 30 ottobre si conservano quelle dal 30 settembre. La pulizia avviene all’avvio, ogni giorno a server attivo e alla lettura agenda; se il server è spento, alla successiva accensione. Gli account non scadono dopo un mese. Le copie di backup devono avere una scadenza separata coerente: eliminare dal database non cancella copie già esistenti.

## Dati e sicurezza

Il database locale conserva nome, email, ruolo, stato, impronta scrypt della password con sale casuale e prenotazioni (classe, orari e note). Non vengono conservate password in chiaro. Le sessioni durano 8 ore, usano cookie HttpOnly/SameSite e sono revocate al logout, al cambio password o alla modifica amministrativa di ruolo/stato. Dopo 5 tentativi di login errati sullo stesso indirizzo l’accesso è bloccato temporaneamente per 15 minuti.

Email e nome sono dati personali. Nelle note non inserire dati di alunni o informazioni delicate. I dati non entrano in Git; limitare accesso al file ai responsabili del server. Fare backup con l’API SQLite oppure copiare il file a server fermo. Il workspace di sviluppo non è un servizio di hosting e non sostituisce il backup.

Migrazione: gli utenti delle versioni precedenti passano in attesa di approvazione quando viene aggiunto il campo stato. I dati e i laboratori esistenti vengono conservati. Le vecchie prenotazioni senza proprietario sono gestibili dall’amministratore. Eventuali campi Google storici non sono usati per autenticazione. `GOOGLE_CLIENT_ID` e `TEACHER_EMAILS` non sono più necessari.

## Test

```sh
python3 -m unittest discover -s tests -v
```

I test usano database temporanei e controllano persistenza, orari, finestra temporale, conservazione, conflitti, accessi, registrazione, approvazione, esclusione, ruoli, protezione dell’ultimo amministratore, password e gestione amministrativa delle prenotazioni. I test HTTP richiedono socket locali.

## Accesso dalla scuola e da casa

Per l’hosting WSGI con database fuori dalla cartella dei sorgenti, seguire [PYTHONANYWHERE.md](PYTHONANYWHERE.md). Non sono necessari un server sempre acceso a scuola o porte aperte nel router. `wsgi.py` espone l’app senza avviare il server di sviluppo. `backup.py` crea copie SQLite consistenti e ne verifica l’integrità; non sovrascrive copie già esistenti.

## Calendario settimanale e mensile

Dopo l’accesso, il pulsante **Calendario settimana e mese** è visibile in alto nella schermata principale. La settimana mostra tutti e sette i giorni e le sei fasce 08–14, con tutte le prenotazioni dei diversi laboratori anche nella stessa ora. La vista mese mostra ogni giorno e tutte le sue prenotazioni, inclusi i giorni adiacenti necessari a completare le settimane. Un filtro indipendente permette di scegliere un laboratorio; i colori e la legenda distinguono gli spazi. Ogni prenotazione mostra orario, laboratorio, docente e classe. Cliccando si aprono i dettagli; dal dettaglio si può aprire quel giorno nell’agenda per le operazioni già autorizzate.

Sono disponibili precedente/successivo, Oggi, scelta data e Aggiorna. Il calendario usa gli stessi dati dell’agenda e non estende il periodo di conservazione: i giorni fuori dalla finestra disponibile sono indicati esplicitamente. Il riepilogo conta le prenotazioni della settimana o del mese selezionato, escludendo i giorni adiacenti di altri mesi. Sui telefoni la griglia scorre orizzontalmente. L’accesso rimane riservato agli utenti attivi.

La verifica opzionale del calendario nel browser è in `tests/browser_calendar.py`: richiede Playwright e Chromium nell’ambiente di sviluppo, senza aggiungere dipendenze al server. Si esegue con `python3 tests/browser_calendar.py` e usa esclusivamente un database temporaneo.

## Prova completa di persistenza nel browser

`python3 tests/browser_persistence.py` (Playwright e Chromium richiesti solo per questo test) crea account e prenotazioni su database temporaneo esterno ai sorgenti, chiude completamente il browser, termina il processo WSGI e avvia un nuovo processo con lo stesso database. Una nuova sessione browser deve ritrovare account e prenotazioni in agenda e calendario; viene verificata anche l’integrità SQLite. La suite standard controlla inoltre la concorrenza tra docenti: due richieste simultanee sulle stesse ore producono un unico salvataggio e un conflitto senza record parziali.

Queste verifiche riguardano il codice nell’ambiente di sviluppo. Sul sito PythonAnywhere, dopo ogni aggiornamento verificare anche la pagina con i dispositivi effettivamente usati a scuola: creare una prenotazione di prova, chiudere il browser, premere Web → Reload e riaprire il sito. Il database deve continuare a essere quello persistente esterno ai sorgenti configurato nel file WSGI. Connessione, disponibilità e rinnovo del piano hosting rimangono condizioni esterne; nessun test garantisce qualsiasi browser, rete o carico. La cancellazione dello storico oltre un mese rimane intenzionale.

## Identità della scuola e regolamenti

Il titolo è **Laboratori IC2 Giovanni Paolo II di Policoro** e il sottotitolo **Pianifica le attività e prenota il laboratorio**. La palette principale riprende arancio, oro, bianco e toni scuri dell’identità scolastica fornita. La home mostra l’intestazione completa; calendario e pagine dei regolamenti mostrano solo il logo. Le immagini originali ricevute nello ZIP sono incluse nel progetto senza modifiche: `web/assets/school-header.jpg` e `web/assets/school-logo.png`. Vengono importate automaticamente nel database alla prima installazione e negli aggiornamenti dove mancano; eventuali immagini già caricate dall’amministratore non vengono sovrascritte.

L’amministratore può aprire **Identità della scuola e regolamento** e caricare separatamente intestazione completa e logo (PNG/JPG/WebP, massimo 2 MB ciascuno). Le immagini sono conservate nel database persistente: il caricamento non richiede modifiche al codice o un nuovo pacchetto. Non occorre caricare manualmente le immagini iniziali: intestazione e logo sono già forniti nel progetto. Il pannello rimane disponibile per eventuali sostituzioni successive.

La sezione **Regolamenti**, raggiungibile dal pulsante Regolamenti nella navigazione principale, contiene dieci capitoli sintetici, con indice, collegamenti diretti, pagine testuali per argomento e navigazione fra i capitoli. Il testo mantiene le disposizioni essenziali e i riferimenti dell’originale. La doppia numerazione “Art. 7” dell’originale è segnalata, non corretta arbitrariamente.

Il file originale `documents/regolamento-laboratori.docx` è una copia byte per byte del documento fornito, senza modifiche. Al primo avvio viene importato nel database e reso scaricabile nella sezione Regolamenti per gli utenti autenticati e approvati. La sintesi iniziale è in `documents/regulations-summary.json`. Tutti i documenti sono contenuti scolastici, non istruzioni operative per il server.

Gli amministratori possono sostituire il regolamento completo con PDF, DOCX o TXT UTF-8 (massimo 5 MB). Un nuovo caricamento incrementa la versione e aggiorna il link scaricabile. La sintesi è indicata come **in revisione** fino a quando un amministratore non controlla, modifica se necessario e salva i capitoli per il documento attuale. Nessuna nuova sintesi viene inventata automaticamente. Gli amministratori modificano titoli, riferimenti e paragrafi con normali campi di testo, senza HTML o codice. Docenti e iscritti non approvati non possono modificare i documenti; gli iscritti non approvati non possono scaricarli.

Documenti, sintesi e immagini sono inclusi nel backup SQLite; i successivi avvii non sovrascrivono i caricamenti amministrativi con le copie iniziali del progetto. Quando si aggiorna questa versione sul sito, estrarre lo ZIP completo (inclusi `school.py`, `documents/` e il nuovo `wsgi.py`), conservare la directory `laboratori-data` e premere Web → Reload. È consigliato un backup prima dell’aggiornamento.

La suite standard include i test di documenti, versionamento, permessi, integrità del download originale, limiti dei caricamenti e persistenza delle immagini. La verifica opzionale `python3 tests/browser_school.py` usa Playwright/Chromium e dati temporanei per verificare i flussi completi nel browser, compresi i download e la navigazione mobile.

## Ordine della schermata principale

Dopo l’accesso, la prima area operativa è **Prenotazioni e agenda**, con il modulo di prenotazione e l’elenco. L’amministrazione si apre dal pulsante **Amministrazione**, accanto a **Regolamenti** nella navigazione principale, visibile soltanto agli amministratori. Il pannello non compare sotto le prenotazioni. Al suo interno **Iscrizioni e permessi docenti** è una sezione inizialmente chiusa ed espandibile, con ricerca, tutte le azioni di gestione e il sottomenu **Crea un amministratore o docente**. Anche **Gestisci laboratori** usa lo stesso riquadro espandibile degli altri menu amministrativi. Il cambio password si trova nella sezione **Profilo** della navigazione principale. Nessun riquadro o download del regolamento compare dentro Prenotazioni e agenda: indice e documento completo si trovano soltanto nella sezione Regolamenti, raggiungibile dal pulsante nella navigazione principale.

## Sospensione temporanea di un laboratorio

In **Amministrazione → Gestisci laboratori**, **Sospendi temporaneamente** apre una finestra con il campo obbligatorio **Comunicazione agli utenti** (massimo 1000 caratteri). L’amministratore inserisce il motivo e conferma. Il laboratorio resta nell’elenco dei docenti, contrassegnato come temporaneamente sospeso. Alla selezione nel modulo di prenotazione, l’app ricontrolla lo stato corrente sul server e mostra un pop-up con il testo esatto della comunicazione; il messaggio resta leggibile anche nel modulo. Le ore e il salvataggio sono disabilitati.

La protezione è applicata anche dal server: se la sospensione viene impostata mentre un docente sta compilando una prenotazione, il salvataggio viene rifiutato senza creare record parziali e il modulo recupera il messaggio aggiornato. Il blocco vale anche per le nuove prenotazioni amministrative e per la modifica di quelle esistenti. Le prenotazioni già registrate restano visibili e non vengono cancellate automaticamente; l’amministratore può gestirne l’annullamento separatamente.

**Modifica comunicazione** aggiorna il motivo. **Termina sospensione** riapre le prenotazioni e rimuove il messaggio. La sospensione non ha una scadenza automatica e rimane fino alla riattivazione manuale. La disattivazione ordinaria rimane distinta: nasconde il laboratorio dal modulo. Stato e messaggio della sospensione sono conservati nel database e inclusi nel backup.

I test standard verificano persistenza, messaggi, permessi, conservazione delle prenotazioni e riattivazione. La prova opzionale `python3 tests/browser_suspension.py` usa due sessioni browser indipendenti, amministratore e docente, comprese una sospensione durante la compilazione e la vista mobile.

## Backup scaricabile, chiusure e report

Gli amministratori trovano **Amministrazione → Backup completo → Scarica backup SQLite**. Il download usa l’API di backup SQLite e ne verifica l’integrità mentre il sito resta attivo. Include account, sessioni, prenotazioni, chiusure, immagini e documenti: custodire il file come dato riservato e definire una scadenza delle copie. L’accesso è controllato dal server ed è riservato agli amministratori attivi.

In **Calendario delle chiusure**, scegliere il mese e spuntare uno o più giorni (oppure tutti i giorni del mese), scrivere una comunicazione e salvare. **Blocca prenotazioni** e **Visibile ai docenti** sono indipendenti: è possibile pubblicare un avviso senza blocco oppure bloccare una data senza pubblicare la comunicazione. Per ogni giorno già salvato si possono cambiare le due spunte, modificare il testo o rimuovere la chiusura. La rimozione riapre la data soltanto se le altre regole permettono di prenotare. Le chiusure non cancellano le prenotazioni esistenti: l’amministratore le gestisce separatamente. La validazione sul server blocca anche richieste dirette e modifiche dirette verso le date chiuse. I docenti vedono le comunicazioni pubblicate in agenda e calendario; per una data bloccata non pubblicata ricevono soltanto l’indicazione generica di indisponibilità, senza il testo riservato. Le date indisponibili sono comunicate al modulo per disabilitare le ore.

**Le mie prenotazioni** filtra l’agenda o il calendario usando l’account proprietario. I docenti possono scegliere **Modifica** sulle proprie prenotazioni, mantenendo il medesimo record e proprietario; possono cambiare laboratorio, data, singola ora, classe e note entro le regole ordinarie. I controlli su proprietà, disponibilità e aggiornamento avvengono nella stessa transazione. Gli amministratori conservano la gestione delle prenotazioni di tutti.

Il riquadro **Stampa e PDF delle prenotazioni** è disponibile a tutti gli utenti approvati e attivi nella pagina **Prenotazioni e agenda**: si trova nella colonna sinistra, subito sotto il modulo di prenotazione, con campi e pulsanti disposti in verticale. Nel **Calendario** lo stesso riquadro compare nella colonna sinistra; non compare in Regolamenti, Profilo o Amministrazione. I valori selezionati si conservano passando tra agenda e calendario. Su telefono i riquadri si dispongono uno sotto l’altro. Scegliere data di riferimento, giorno/settimana/mese e prenotazioni personali/generali. La settimana va da lunedì a domenica, il mese dal primo all’ultimo giorno. **Apri stampa** apre una pagina dedicata con il comando di stampa del browser; **Scarica PDF** genera direttamente un PDF A4 con pagine numerate. Entrambi includono le comunicazioni visibili, senza dipendere dai filtri dell’agenda. I report utilizzano soltanto lo storico ancora conservato e non recuperano le prenotazioni eliminate dalla pulizia mensile. I documenti hanno intestazione scolastica ripetuta sulle pagine, titoli e date in evidenza, etichette in grassetto e note in corsivo. I PDF incorporano i font Vera e numerano le pagine; i testi vengono mandati a capo senza troncare le note.

Compatibile con Python 3.12 e WSGI PythonAnywhere. Installare `requirements.txt` per generare i report con immagini e impaginazione: `python3.12 -m pip install --user -r requirements.txt`. All’avvio viene aggiunta la tabella delle chiusure senza sostituire il database o i dati esistenti. Il modulo `reports.py` deve essere caricato insieme ai sorgenti aggiornati.

Test aggiuntivi: `tests/test_planning.py` verifica permessi, modifiche, chiusure indipendenti, backup e report tramite WSGI. La prova opzionale `python3 tests/browser_planning.py` verifica i nuovi flussi completi in Chromium, inclusi download, stampa e mobile.

La prova opzionale `python3 tests/browser_admin_navigation.py` verifica il menu Amministrazione, l’elenco iscritti inizialmente chiuso, ricerca e approvazione, ritorno alle prenotazioni, vista mobile e assenza del menu per i docenti.

## Agenda semplificata e tutte le date

Il riquadro ripetuto “Laboratori della scuola” è stato rimosso: l’elenco rimane nella scelta del laboratorio. Nell’agenda **Mostra tutte le date** elimina soltanto il filtro del giorno, mantenendo il laboratorio scelto (o Tutti i laboratori) e la spunta **Le mie prenotazioni**. Il pulsante diventa **Torna al [giorno]**: premendolo si ripristina il giorno precedente mantenendo i filtri di laboratorio e proprietà correnti. Si può cambiare laboratorio anche mentre si consultano tutte le date. Scegliendo manualmente un giorno si torna subito alla visualizzazione giornaliera. Un riepilogo mostra sempre i filtri applicati. “Tutte le date” comprende soltanto le prenotazioni ancora conservate nell’app.

La prova opzionale `python3 tests/browser_agenda_filters.py` verifica combinazioni di date, laboratori e prenotazioni personali, ritorno al giorno precedente, aggiornamento dei dati e navigazione dal calendario.

## Profilo personale

**Profilo** mostra esclusivamente i dati dell’utente collegato: nome, email di accesso, ruolo, stato di approvazione, scadenza della sessione in ora italiana e conteggio delle proprie prenotazioni conservate. Un pulsante apre le proprie prenotazioni nell’agenda. Nome, email e ruolo sono consultabili; non è previsto un cambio autonomo di ruolo o approvazione.

Il modulo di cambio password è stato spostato qui dalla pagina principale: richiede la password corrente e la conferma della nuova, e revoca tutte le sessioni dopo il salvataggio. Nessuna password esistente viene visualizzata.

Per gli amministratori il profilo include un riepilogo delle autorizzazioni, il numero di iscritti in attesa e di amministratori attivi, il richiamo alla protezione dell’ultimo amministratore e il collegamento ad Amministrazione. Nessun dato aggiuntivo viene richiesto e non sono necessarie migrazioni del database.

La prova opzionale `python3 tests/browser_profile.py` verifica i profili docente e amministratore, la visualizzazione dei soli dati personali, i collegamenti, il cambio password, la revoca delle altre sessioni e la vista mobile.

## Notifiche iscrizioni in attesa

Gli amministratori vedono un numerino su **Amministrazione** e sul menu **Iscrizioni e permessi docenti**. Il numero rappresenta gli account attualmente in attesa di approvazione, non le richieste semplicemente non lette: aprire il menu non lo cancella. Approvando, escludendo o eliminando una richiesta il conteggio diminuisce; quando arriva a zero il numerino scompare. Gli account attivi o esclusi non vengono contati.

Il conteggio si aggiorna dopo le operazioni amministrative, ogni 30 secondi mentre la pagina è visibile e quando si torna alla scheda o alla pagina principale. La verifica periodica scarica soltanto il conteggio, tramite un’API riservata agli amministratori. I docenti e gli utenti non autenticati non possono consultarlo.

La prova opzionale `python3 tests/browser_registration_notifications.py` verifica i due numerini, l’aggiornamento automatico dopo una registrazione da un’altra sessione, approvazione ed eliminazione, assenza completa degli indicatori a zero, protezione dalle risposte obsolete, vista mobile e accesso riservato.

Il calendario settimanale mantiene tutti e sette i giorni, con colonne più compatte per sabato e domenica e spazio dedicato ai cinque giorni prenotabili. Sui tablet il calendario occupa l’intera larghezza disponibile, sotto il riquadro di stampa; sui telefoni si scorre soltanto la griglia. Le schede delle prenotazioni mandano a capo i testi lunghi senza troncarli.

I report usano l’immagine **intestazione** corrente conservata nel database, comprese le sostituzioni caricate dall’amministratore. JPEG, PNG e WebP vengono preparati per la stampa senza alterare le proporzioni. Se un’immagine caricata non è decodificabile viene usata l’intestazione originale del progetto. I dati delle prenotazioni non vengono trasformati in maiuscolo: maiuscole e grassetti distinguono solo titoli, date ed etichette.
