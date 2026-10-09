document.addEventListener("DOMContentLoaded", () => {
  const scanner = document.querySelector("[data-verification-scanner]");
  if (!scanner) return;

  const startButton = scanner.querySelector("[data-scan-start]");
  const stopButton = scanner.querySelector("[data-scan-stop]");
  const status = scanner.querySelector("[data-scan-status]");
  const video = scanner.querySelector("[data-scan-video]");
  const verifyUrl = scanner.dataset.verifyUrl;
  let stream = null;
  let scanning = false;

  const stopScanner = () => {
    scanning = false;
    if (stream) {
      for (const track of stream.getTracks()) track.stop();
      stream = null;
    }
    video.srcObject = null;
    video.hidden = true;
    stopButton.hidden = true;
    startButton.hidden = false;
  };

  stopButton.addEventListener("click", () => {
    stopScanner();
    status.textContent = "Scanner arrêté.";
  });

  startButton.addEventListener("click", async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      status.textContent = "La caméra nécessite un navigateur compatible et une connexion sécurisée.";
      return;
    }
    if (!("BarcodeDetector" in window)) {
      status.textContent = "La lecture QR n'est pas prise en charge par ce navigateur. Saisissez le code manuellement.";
      return;
    }

    try {
      const detector = new BarcodeDetector({ formats: ["qr_code"] });
      stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" } },
      });
      video.srcObject = stream;
      video.hidden = false;
      stopButton.hidden = false;
      startButton.hidden = true;
      status.textContent = "Pointez la caméra vers le code QR du document.";
      await video.play();
      scanning = true;

      const scanFrame = async () => {
        if (!scanning) return;
        if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
          try {
            const [barcode] = await detector.detect(video);
            if (barcode) {
              let code = barcode.rawValue.trim();
              try {
                const qrUrl = new URL(code, window.location.origin);
                const segments = qrUrl.pathname.split("/").filter(Boolean);
                const verificationIndex = segments.indexOf("verification");
                if (verificationIndex >= 0 && segments[verificationIndex + 1]) {
                  code = decodeURIComponent(segments[verificationIndex + 1]);
                }
              } catch {
              }
              stopScanner();
              window.location.assign(verifyUrl.replace("SCAN_CODE", encodeURIComponent(code)));
              return;
            }
          } catch {
            status.textContent = "Lecture en cours… gardez le code dans le cadre.";
          }
        }
        requestAnimationFrame(scanFrame);
      };

      requestAnimationFrame(scanFrame);
    } catch {
      stopScanner();
      status.textContent = "Impossible d'accéder à la caméra. Vérifiez son autorisation ou saisissez le code manuellement.";
    }
  });
});