## 🧠 Analisi Metodologica e Standard di Progettazione HRS

**Il "Reality Check" Tecnico:**
Progettare una stazione di rifornimento a idrogeno (HRS) non è come costruire un distributore diesel. L'idrogeno è un gas che richiede di essere compresso a pressioni estreme (fino a 900-1000 bar per le auto) e pre-raffreddato fino a -40°C per evitare che i serbatoi dei veicoli si surriscaldino ed esplodano durante il riempimento rapido (secondo il rigido protocollo internazionale **SAE J2601**).

**I 3 Pilastri del Dimensionamento:**

1. **La Termodinamica del Freddo e della Pressione:** Il vero collo di bottiglia di una HRS non è "quanta molecola si ha a disposizione", ma *quanto velocemente* i compressori riescono a ricaricare i serbatoi di stoccaggio in piazzale. L'erogazione alla pompa è fisicamente limitata a 60 g/s (700 bar) o 120 g/s (350 bar). Oltre non si può andare.
2. **Architettura di Routing:**
   * *Magazzino a Cascata:* Usa enormi serbatoi divisi su 3 livelli di pressione. Riempie il veicolo "travasando" il gas per differenza di pressione. Alza enormemente il costo iniziale (CAPEX), ma permette di fare rifornimenti consecutivi senza far aspettare i camion in coda.
   * *Booster Diretto:* Il compressore spinge il gas direttamente nella pompa. Costa meno in termini di serbatoi, ma richiede compressori titanici (e molto energivori) per tenere il passo della pompa.
3. **La Trappola del Break-Even (Fattore di Carico):** I costi operativi di manutenzione (OPEX) e le rate di ammortamento dei compressori sono brutali. Se la stazione lavora a meno del 50-60% della sua capacità teorica, il "Sovrapprezzo HRS" (la quota da sommare al costo della molecola per ripagare l'impianto) schizza facilmente sopra i 5-6 €/kg, rendendo l'idrogeno economicamente invendibile. **Serve una domanda locale (flotte) blindata da contratti prima ancora di gettare il cemento.**