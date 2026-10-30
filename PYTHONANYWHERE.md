# Pubblicazione con dati persistenti

Queste istruzioni preparano un sito raggiungibile dalla scuola e da casa. L’agenda richiede accesso approvato dall’amministratore. Il PC della scuola usa il browser e non deve rimanere acceso. Verificare condizioni, scadenze, rinnovi manuali, spazio disco e HTTPS del piano di hosting scelto: non sono garantiti dal progetto.

## 1. Account e caricamento

Creare l’account su PythonAnywhere senza comunicare la password in chat. Annotare lo username e il dominio effettivamente assegnato. Se l’account è sul servizio europeo, usare il dominio indicato dal proprio pannello, senza dedurlo da esempi.

Nella scheda **Files**, caricare `laboratori-pythonanywhere.zip` nella propria cartella principale. Nella scheda **Consoles** aprire una console **Bash** ed eseguire:

```bash
python3 -m zipfile -e "$HOME/laboratori-pythonanywhere.zip" "$HOME/laboratori-app"
mkdir -p "$HOME/laboratori-data"
```

La cartella `laboratori-app` deve contenere `app.py`, `wsgi.py` e `web/index.html`. Lo ZIP non contiene database, password, codice monouso o dati di prova.

## 2. Sito Web

Nella scheda **Web** scegliere **Add a new web app**, il dominio fornito, **Manual configuration** e Python **3.12 o successivo**. Non selezionare un’app Flask/Django di esempio.

Aprire il collegamento al **WSGI configuration file**. Sostituire il suo contenuto con:

```python
import os
import sys
from pathlib import Path

project = Path.home() / 'laboratori-app'
sys.path.insert(0, str(project))
os.environ['LAB_DB'] = str(Path.home() / 'laboratori-data' / 'laboratori.sqlite3')
os.environ['COOKIE_SECURE'] = '1'
from wsgi import application
```

Salvare, attivare l’opzione **Force HTTPS** se disponibile nel pannello e premere **Reload**. Aprire il dominio assegnato usando `https://`. Non aggiungere mapping statici verso `laboratori-data`, verso la cartella principale o verso tutto il progetto: database e codice monouso devono rimanere privati. Non avviare `python3 app.py` per far funzionare il sito: l’hosting usa WSGI.

Se appare un errore, leggere il collegamento **Error log** nella scheda Web; condividere soltanto il messaggio necessario, senza password o codici monouso.

## 3. Primo amministratore

La pagina iniziale mostra Rosario Calabrese e rosariocalabrese80@gmail.com. Dal pannello **Files** aprire privatamente `laboratori-data/laboratori.setup-token`. Copiare il codice nel modulo del sito e scegliere una password di almeno 6 caratteri con conferma. Non pubblicare il codice o la password. Il codice generato nella macchina cloud di sviluppo non vale su questo nuovo sito.

Il file monouso viene eliminato dopo la configurazione. Accedere con email e password scelte. Gli altri utenti si registrano da soli, con qualsiasi email, e sono abilitati dall’amministratore dopo il controllo degli elenchi.

## 4. Prova di persistenza obbligatoria

1. Registrare un docente di prova dal sito e approvarlo come amministratore.
2. Inserire una prenotazione valida e annotare laboratorio, data e ora.
3. Premere **Reload** nella scheda Web dell’hosting, chiudere la pagina e riaprirla.
4. Accedere e controllare che account e prenotazione siano ancora presenti.
5. Aprire lo stesso sito da un altro dispositivo, anche tramite rete mobile, e controllare la medesima prenotazione.
6. Eliminare i dati di prova prima dell’utilizzo effettivo.

Il database è `/home/TUO_USERNAME/laboratori-data/laboratori.sqlite3`: è fuori dalla cartella del codice. Un riavvio o un aggiornamento dei soli sorgenti non lo cancella. La conservazione dipende comunque dal mantenimento dell’account e dal rispetto delle condizioni dell’hosting.

## 5. Backup e aggiornamenti

Prima di un aggiornamento, dalla console Bash creare una copia consistente (anche con sito acceso):

```bash
LAB_DB="$HOME/laboratori-data/laboratori.sqlite3" python3 "$HOME/laboratori-app/backup.py" "$HOME/laboratori-backup-$(date +%Y%m%d-%H%M%S).sqlite3"
```

Scaricare il file dal pannello Files su un supporto custodito dalla scuola. Un backup solo sullo stesso account non protegge dalla perdita dell’account. Il comando verifica l’integrità e rifiuta di sovrascrivere un file esistente. Per il ripristino, fermare temporaneamente l’app e sostituire il database con la copia verificata; non eseguire il ripristino mentre l’app scrive.

Aggiornare solo `laboratori-app`, conservando `laboratori-data`. Non caricare database vuoti sopra quello reale e non cancellare quella directory. Gestire una scadenza esplicita anche dei backup scaricati: lo storico dell’app elimina le prenotazioni anteriori a un mese, ma non può cancellare copie già create. Su WSGI la pulizia avviene all’avvio dei worker e alla lettura dell’agenda; senza accessi o riavvii non è garantita una cancellazione all’esatta mezzanotte.

Le prove locali confermano persistenza e compatibilità WSGI; la pubblicazione e la prova sul proprio account devono ancora essere eseguite.
