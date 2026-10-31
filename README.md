# Prenotazioni laboratori scolastici

App da browser per i cinque laboratori della scuola, con SQLite gratuito su disco, registrazione autonoma e amministrazione. Richiede Python 3.12 o successivo e solo la libreria standard. Nessun servizio Google o servizio email necessario.

## Primo avvio

```sh
cd /workspace/APP-LABORATORI-SCUOLA
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

Le autorizzazioni sono controllate anche dal server. I docenti attivi vedono l’agenda ma possono annullare soltanto le proprie prenotazioni. Possono cambiare password con verifica di quella attuale; tutte le sessioni terminano dopo il cambio. Per password dimenticata ci si rivolge all’amministratore, senza recupero automatico via email.

## Laboratori e regole

Catalogo iniziale: Informatica aula 133; STEM/Coding aula 132; Arte aula 131; Informatica carrello mobile n. 1; Informatica carrello mobile n. 2. Il catalogo viene inizializzato una volta: le modifiche amministrative sono conservate ai successivi avvii.

Prenotazioni di un’ora intera, lunedì–venerdì, nelle fasce 08–09, 09–10, 10–11, 11–12, 12–13, 13–14. Il modulo permette di spuntare più fasce orarie dello stesso giorno, anche non consecutive. Un solo salvataggio crea una prenotazione distinta per ogni ora. Le ore già occupate sono disabilitate; il server ricontrolla la disponibilità al salvataggio e, in caso di conflitto su una qualsiasi ora, non salva nessuna delle ore selezionate. La modifica amministrativa riguarda una prenotazione alla volta. Sono bloccate frazioni, sovrapposizioni e fine settimana; festività e chiusure straordinarie non sono configurate.

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

Dopo l’accesso, la prima area operativa è **Prenotazioni e agenda**, con il modulo di prenotazione e l’elenco. Anche per gli amministratori questo blocco precede il pannello amministrativo; amministrazione e cambio password seguono più in basso. Nessun riquadro o download del regolamento compare dentro Prenotazioni e agenda: indice e documento completo si trovano soltanto nella sezione Regolamenti, raggiungibile dal pulsante nella navigazione principale.
