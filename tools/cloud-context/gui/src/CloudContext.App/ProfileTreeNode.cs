using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using CloudContext.Core;

namespace CloudContext.App;

public sealed class ProfileTreeNode : INotifyPropertyChanged
{
    private bool _isExpanded = true;
    private bool _isSelected;

    public ProfileTreeNode(string name, CloudProfile? profile = null)
    {
        Name = name;
        Profile = profile;
    }

    public string Name { get; }

    public CloudProfile? Profile { get; }

    public ObservableCollection<ProfileTreeNode> Children { get; } = [];

    public bool IsExpanded
    {
        get => _isExpanded;
        set => SetField(ref _isExpanded, value);
    }

    public bool IsSelected
    {
        get => _isSelected;
        set => SetField(ref _isSelected, value);
    }

    public event PropertyChangedEventHandler? PropertyChanged;

    private void SetField(ref bool field, bool value, [CallerMemberName] string? propertyName = null)
    {
        if (field == value)
        {
            return;
        }

        field = value;
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
