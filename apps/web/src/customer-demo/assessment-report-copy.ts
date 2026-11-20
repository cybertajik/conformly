import type { SupportedLocale } from "../i18n/types";
import type { ReportErrorCode } from "./assessment-report-api";

interface ReportCopy {
  title: string; description: string; contents: string; download: string; preparing: string;
  cancel: string; prepared: string; missing: string; denied: string;
  errors: Record<ReportErrorCode, string>;
}
export const reportCopy: Record<SupportedLocale, ReportCopy> = {
  en: {
    title: "Assessment report", description: "Download a private snapshot of the selected adoption. This synthetic report is not certification or a frozen pre-audit result.",
    contents: "ZIP includes an English HTML report, JSON metadata and a SHA-256 manifest. Evidence files and private narratives are excluded.",
    download: "Download report", preparing: "Preparing and verifying report…", cancel: "Cancel",
    prepared: "Download handed to your browser. Check your downloads.",
    missing: "Select a current adopted scope before downloading.", denied: "This session cannot download assessment reports.",
    errors: { invalid: "The selected scope is incomplete.", unauthorized: "Your session expired. Sign in again.", forbidden: "You do not have access to this report.",
      conflict: "The scope changed or is unavailable. Refresh the workspace before retrying.", unavailable: "The report could not be prepared. Try again.",
      integrity: "The report could not be verified. No file was downloaded.", crypto: "A secure browser context is required to verify this download. Use HTTPS or localhost." },
  },
  de: {
    title: "Bewertungsbericht", description: "Laden Sie eine private Momentaufnahme des ausgewählten Geltungsbereichs herunter. Dieser synthetische Bericht ist keine Zertifizierung und kein eingefrorenes Vorprüfungsergebnis.",
    contents: "Die ZIP-Datei enthält einen englischen HTML-Bericht, JSON-Metadaten und ein SHA-256-Manifest. Nachweisdateien und vertrauliche Erläuterungen sind ausgeschlossen.",
    download: "Bericht herunterladen", preparing: "Bericht wird erstellt und geprüft…", cancel: "Abbrechen",
    prepared: "Download an den Browser übergeben. Prüfen Sie Ihre Downloads.",
    missing: "Wählen Sie zuerst einen aktuellen übernommenen Geltungsbereich.", denied: "Diese Sitzung darf keine Bewertungsberichte herunterladen.",
    errors: { invalid: "Der ausgewählte Geltungsbereich ist unvollständig.", unauthorized: "Ihre Sitzung ist abgelaufen. Melden Sie sich erneut an.", forbidden: "Sie haben keinen Zugriff auf diesen Bericht.",
      conflict: "Der Geltungsbereich wurde geändert oder ist nicht verfügbar. Aktualisieren Sie den Arbeitsbereich.", unavailable: "Der Bericht konnte nicht erstellt werden. Versuchen Sie es erneut.",
      integrity: "Der Bericht konnte nicht verifiziert werden. Es wurde keine Datei heruntergeladen.", crypto: "Zur Prüfung ist ein sicherer Browserkontext erforderlich. Verwenden Sie HTTPS oder localhost." },
  },
  fr: {
    title: "Rapport d’évaluation", description: "Téléchargez un instantané privé du périmètre adopté. Ce rapport synthétique ne constitue ni une certification ni un résultat de pré-audit figé.",
    contents: "Le ZIP contient un rapport HTML en anglais, des métadonnées JSON et un manifeste SHA-256. Les pièces justificatives et récits privés sont exclus.",
    download: "Télécharger le rapport", preparing: "Préparation et vérification du rapport…", cancel: "Annuler",
    prepared: "Téléchargement transmis au navigateur. Consultez vos téléchargements.",
    missing: "Sélectionnez d’abord un périmètre adopté actuel.", denied: "Cette session ne peut pas télécharger de rapports.",
    errors: { invalid: "Le périmètre sélectionné est incomplet.", unauthorized: "Votre session a expiré. Reconnectez-vous.", forbidden: "Vous n’avez pas accès à ce rapport.",
      conflict: "Le périmètre a changé ou est indisponible. Actualisez l’espace de travail.", unavailable: "Le rapport n’a pas pu être préparé. Réessayez.",
      integrity: "Le rapport n’a pas pu être vérifié. Aucun fichier téléchargé.", crypto: "Un contexte sécurisé est requis pour vérifier le téléchargement. Utilisez HTTPS ou localhost." },
  },
  nl: {
    title: "Beoordelingsrapport", description: "Download een privé-momentopname van het gekozen toepassingsgebied. Dit synthetische rapport is geen certificering of vastgelegd voorauditresultaat.",
    contents: "De ZIP bevat een Engels HTML-rapport, JSON-metadata en een SHA-256-manifest. Bewijsbestanden en vertrouwelijke toelichtingen zijn uitgesloten.",
    download: "Rapport downloaden", preparing: "Rapport voorbereiden en controleren…", cancel: "Annuleren",
    prepared: "Download doorgegeven aan uw browser. Controleer uw downloads.",
    missing: "Selecteer eerst een actueel aangenomen toepassingsgebied.", denied: "Deze sessie mag geen beoordelingsrapporten downloaden.",
    errors: { invalid: "Het gekozen toepassingsgebied is onvolledig.", unauthorized: "Uw sessie is verlopen. Meld u opnieuw aan.", forbidden: "U heeft geen toegang tot dit rapport.",
      conflict: "Het toepassingsgebied is gewijzigd of niet beschikbaar. Vernieuw de werkruimte.", unavailable: "Het rapport kon niet worden voorbereid. Probeer opnieuw.",
      integrity: "Het rapport kon niet worden geverifieerd. Er is geen bestand gedownload.", crypto: "Een veilige browsercontext is vereist. Gebruik HTTPS of localhost." },
  },
  es: {
    title: "Informe de evaluación", description: "Descargue una instantánea privada del ámbito adoptado. Este informe sintético no es una certificación ni un resultado de preauditoría congelado.",
    contents: "El ZIP incluye un informe HTML en inglés, metadatos JSON y un manifiesto SHA-256. Se excluyen archivos de evidencia y relatos privados.",
    download: "Descargar informe", preparing: "Preparando y verificando el informe…", cancel: "Cancelar",
    prepared: "Descarga enviada al navegador. Revise sus descargas.",
    missing: "Seleccione primero un ámbito adoptado actual.", denied: "Esta sesión no puede descargar informes de evaluación.",
    errors: { invalid: "El ámbito seleccionado está incompleto.", unauthorized: "Su sesión ha caducado. Inicie sesión de nuevo.", forbidden: "No tiene acceso a este informe.",
      conflict: "El ámbito ha cambiado o no está disponible. Actualice el espacio de trabajo.", unavailable: "No se pudo preparar el informe. Inténtelo de nuevo.",
      integrity: "No se pudo verificar el informe. No se descargó ningún archivo.", crypto: "Se requiere un contexto seguro para verificar la descarga. Utilice HTTPS o localhost." },
  },
};

