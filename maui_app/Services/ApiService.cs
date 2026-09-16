using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace RpaAgentApp.Services;

/// <summary>
/// Servicio que se comunica con la FastAPI del backend.
/// Centralizo toda la logica HTTP aqui para que los ViewModels
/// no tengan que saber nada de endpoints ni serialización.
/// </summary>
public class ApiService
{
    private readonly HttpClient _client;

    // URL base de la API (configurable, por defecto localhost:8000)
    private const string BaseUrl = "http://127.0.0.1:8500";

    public ApiService()
    {
        _client = new HttpClient
        {
            BaseAddress = new Uri(BaseUrl),
            Timeout = TimeSpan.FromSeconds(120)
        };
    }

    /// <summary>
    /// Envío un mensaje al agente y devuelvo la respuesta con las trazas.
    /// </summary>
    public async Task<ChatResponse> SendMessageAsync(string message, bool debugMode = false, string threadId = "maui-session")
    {
        // _ Construimos la petición JSON con el flag de debug incluido
        var request = new ChatRequest { Message = message, ThreadId = threadId, DebugMode = debugMode };

        try
        {
            var response = await _client.PostAsJsonAsync("/chat", request);
            response.EnsureSuccessStatusCode();

            var result = await response.Content.ReadFromJsonAsync<ChatResponse>();
            return result ?? new ChatResponse { Response = "Sin respuesta del servidor." };
        }
        catch (HttpRequestException ex)
        {
            return new ChatResponse
            {
                Response = $"Error de conexión: {ex.Message}\n¿Está corriendo la API en {BaseUrl}?"
            };
        }
        catch (TaskCanceledException)
        {
            return new ChatResponse { Response = "Timeout: la petición tardó demasiado." };
        }
    }

    /// <summary>
    /// Obtengo la lista de procedimientos disponibles.
    /// </summary>
    public async Task<List<ProcedureItem>> GetProceduresAsync()
    {
        try
        {
            var response = await _client.GetFromJsonAsync<ProceduresResponse>("/procedures");
            return response?.Procedures ?? new List<ProcedureItem>();
        }
        catch
        {
            return new List<ProcedureItem>();
        }
    }

    /// <summary>
    /// Verifico que la API esté levantada.
    /// </summary>
    public async Task<bool> HealthCheckAsync()
    {
        try
        {
            var response = await _client.GetAsync("/health");
            return response.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }
}

// Modelos de datos para serialización JSON

public class ChatRequest
{
    [JsonPropertyName("message")]
    public string Message { get; set; } = string.Empty;

    [JsonPropertyName("thread_id")]
    public string ThreadId { get; set; } = "default";

    [JsonPropertyName("debug_mode")]
    public bool DebugMode { get; set; } = false; // _ <-- Listo para enviar por HTTP a Python
}

public class ChatResponse
{
    [JsonPropertyName("response")]
    public string Response { get; set; } = string.Empty;

    [JsonPropertyName("tool_calls")]
    public List<ToolCall> ToolCalls { get; set; } = new();
}

public class ToolCall
{
    [JsonPropertyName("tool")]
    public string Tool { get; set; } = string.Empty;

    [JsonPropertyName("args")]
    public JsonElement Args { get; set; }
}

public class ProcedureItem
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("titulo")]
    public string Titulo { get; set; } = string.Empty;

    [JsonPropertyName("descripcion")]
    public string Descripcion { get; set; } = string.Empty;

    [JsonPropertyName("parametros")]
    public List<string> Parametros { get; set; } = new();
}

public class ProceduresResponse
{
    [JsonPropertyName("procedures")]
    public List<ProcedureItem> Procedures { get; set; } = new();
}
