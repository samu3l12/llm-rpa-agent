using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;
using RpaAgentApp.Services;

namespace RpaAgentApp.ViewModels;

/// <summary>
/// ViewModel para la pagina de procedimientos.
/// Cargo y muestro la lista de workflows disponibles en el sistema.
/// </summary>
public class ProceduresViewModel : INotifyPropertyChanged
{
    private readonly ApiService _api;

    public ObservableCollection<ProcedureItem> Procedures { get; } = new();

    private bool _isLoading;
    public bool IsLoading
    {
        get => _isLoading;
        set { _isLoading = value; OnPropertyChanged(); }
    }

    private string _statusText = "Cargando...";
    public string StatusText
    {
        get => _statusText;
        set { _statusText = value; OnPropertyChanged(); }
    }

    private bool _isBackendDown = true;

    public ICommand RefreshCommand { get; }

    public ProceduresViewModel()
    {
        _api = new ApiService();
        RefreshCommand = new Command(async () => await LoadProceduresAsync(), () => !IsLoading);
        _ = LoadProceduresAsync();

        // Bucle en segundo plano para recargar automáticamente
        Task.Run(async () =>
        {
            while (true)
            {
                await Task.Delay(5000);
                if (IsLoading) continue;

                var isUp = await _api.HealthCheckAsync();
                
                // Si antes estaba caído y ahora responde, o si la lista está vacía y está online, recargamos
                if ((_isBackendDown && isUp) || (Procedures.Count == 0 && isUp))
                {
                    _isBackendDown = !isUp;
                    await LoadProceduresAsync();
                }
                else
                {
                    _isBackendDown = !isUp;
                }
            }
        });
    }

    public async Task LoadProceduresAsync()
    {
        IsLoading = true;
        StatusText = "Cargando procedimientos...";

        try
        {
            var procedures = await _api.GetProceduresAsync();
            Procedures.Clear();
            foreach (var p in procedures)
            {
                Procedures.Add(p);
            }
            StatusText = $"{Procedures.Count} procedimiento(s) disponible(s)";
        }
        catch (Exception ex)
        {
            StatusText = $"Error: {ex.Message}";
        }
        finally
        {
            IsLoading = false;
        }
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    protected void OnPropertyChanged([CallerMemberName] string? name = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
    }
}
