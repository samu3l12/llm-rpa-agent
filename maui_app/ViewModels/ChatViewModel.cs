using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using RpaAgentApp.Services;

namespace RpaAgentApp.ViewModels;

/// <summary>
/// ViewModel para la pagina de chat.
/// Gestiono la lista de mensajes, el envio al agente y las trazas
/// de tools que devuelve la API.
/// </summary>
public class ChatViewModel : INotifyPropertyChanged
{
    private readonly ApiService _api;

    public ObservableCollection<ChatMessage> Messages { get; } = new();

    private string _inputText = string.Empty;
    public string InputText
    {
        get => _inputText;
        set { _inputText = value; OnPropertyChanged(); OnPropertyChanged(nameof(CanSend)); }
    }

    private bool _isBusy;
    public bool IsBusy
    {
        get => _isBusy;
        set { _isBusy = value; OnPropertyChanged(); OnPropertyChanged(nameof(CanSend)); }
    }

    private string _statusText = "Conectando...";
    public string StatusText
    {
        get => _statusText;
        set { _statusText = value; OnPropertyChanged(); }
    }

    private bool _isBackendDown;
    public bool IsBackendDown
    {
        get => _isBackendDown;
        set { _isBackendDown = value; OnPropertyChanged(); }
    }

    // _ Propiedad bindeada al Switch de la interfaz de usuario
    private bool _isDebugMode;
    public bool IsDebugMode
    {
        get => _isDebugMode;
        set { _isDebugMode = value; OnPropertyChanged(); }
    }

    public bool CanSend => !string.IsNullOrWhiteSpace(InputText) && !IsBusy;

    public ICommand SendCommand { get; }
    public ICommand StartBackendCommand { get; }

    public ChatViewModel()
    {
        _api = new ApiService();
        SendCommand = new Command(async () => await SendMessageAsync(), () => CanSend);
        StartBackendCommand = new Command(async () => await StartBackendAsync());

        // Verifico la conexion al iniciar
        _ = CheckConnectionAsync();

        // _ Bucle infinito en segundo plano para auto-recuperar la UI
        Task.Run(async () =>
        {
            while (true)
            {
                await Task.Delay(5000); // _ Ping al servidor cada 5 segundos
                if (!IsBusy) // Solo compruebo si no estoy en medio de otra petición
                {
                    await CheckConnectionAsync();
                }
            }
        });
    }

    private async Task CheckConnectionAsync()
    {
        var ok = await _api.HealthCheckAsync();
        StatusText = ok ? "Conectado a la API" : "API no disponible (¿uvicorn corriendo?)";
        IsBackendDown = !ok;
    }

    private async Task StartBackendAsync()
    {
        try
        {
            StatusText = "Iniciando servidores...";
            IsBusy = true;

            // Encontrar la raiz del proyecto (subiendo directorios desde bin/Debug/...)
            var baseDir = AppContext.BaseDirectory;
            var dirInfo = new System.IO.DirectoryInfo(baseDir);
            
            while (dirInfo != null && !System.IO.File.Exists(System.IO.Path.Combine(dirInfo.FullName, "requirements.txt")))
            {
                dirInfo = dirInfo.Parent;
            }

            if (dirInfo == null)
            {
                StatusText = "Error: No se encontró la raíz del proyecto.";
                return;
            }

            var projectRoot = dirInfo.FullName;

            // Iniciar servidor web (formulario)
            var startWeb = new System.Diagnostics.ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = "/c start \"Servidor Formulario RPA\" cmd /k \".\\.venv\\Scripts\\activate && python web_form/server.py\"",
                WorkingDirectory = projectRoot,
                UseShellExecute = true
            };
            System.Diagnostics.Process.Start(startWeb);

            // Iniciar FastAPI
            var startApi = new System.Diagnostics.ProcessStartInfo
            {
                FileName = "cmd.exe",
                Arguments = "/c start \"FastAPI Agente RPA\" cmd /k \".\\.venv\\Scripts\\activate && python -m uvicorn api.main:app --host 127.0.0.1 --port 8500\"",
                WorkingDirectory = projectRoot,
                UseShellExecute = true
            };
            System.Diagnostics.Process.Start(startApi);

            // Esperar un poco para que levanten
            await Task.Delay(4000);
            
            await CheckConnectionAsync();
        }
        catch (Exception ex)
        {
            StatusText = $"Error al iniciar backend: {ex.Message}";
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task SendMessageAsync()
    {
        if (string.IsNullOrWhiteSpace(InputText)) return;

        var userMessage = InputText.Trim();
        InputText = string.Empty;

        // Añado el mensaje del usuario
        Messages.Add(new ChatMessage
        {
            Text = userMessage,
            IsUser = true,
            Timestamp = DateTime.Now
        });

        IsBusy = true;
        StatusText = "El agente está pensando...";

        try
        {
            // _ Pasamos el estado del Switch a la capa de servicios HTTP
            var response = await _api.SendMessageAsync(userMessage, IsDebugMode);

            // Si hay trazas de tools y el debug está activo, las muestro
            if (response.ToolCalls.Count > 0 && IsDebugMode)
            {
                var trazas = string.Join("\n",
                    response.ToolCalls.Select(tc => $"🔧 {tc.Tool}({tc.Args})"));

                Messages.Add(new ChatMessage
                {
                    Text = trazas,
                    IsUser = false,
                    IsToolTrace = true,
                    Timestamp = DateTime.Now
                });
            }

            // Añado la respuesta del agente
            Messages.Add(new ChatMessage
            {
                Text = response.Response,
                IsUser = false,
                Timestamp = DateTime.Now
            });

            StatusText = "Listo";
        }
        catch (Exception ex)
        {
            Messages.Add(new ChatMessage
            {
                Text = $"Error: {ex.Message}",
                IsUser = false,
                Timestamp = DateTime.Now
            });
            StatusText = "Error";
        }
        finally
        {
            IsBusy = false;
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? name = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
    }
}

/// <summary>
/// Modelo para un mensaje en el chat.
/// </summary>
public class ChatMessage
{
    public string Text { get; set; } = string.Empty;
    public bool IsUser { get; set; }
    public bool IsToolTrace { get; set; }
    public DateTime Timestamp { get; set; }
    public string TimeString => Timestamp.ToString("HH:mm");
    public string BubbleColor => IsUser ? "#4a6cf7" : (IsToolTrace ? "#2d3748" : "#374151");
    public string TextColor => "#ffffff";
    public string HorizontalAlign => IsUser ? "End" : "Start";
}
