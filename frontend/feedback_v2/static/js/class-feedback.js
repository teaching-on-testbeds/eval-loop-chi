// Class feedback handling
$(document).ready(function() {
    console.log('class-feedback.js loaded');
    
    // Fetch available classes when the document loads
    let availableClasses = [];
    
    $.getJSON('/api/classes', function(data) {
        console.log('Classes received:', data);
        availableClasses = data;
    }).fail(function(jqxhr, textStatus, error) {
        console.error('Error fetching classes:', textStatus, error);
    });
    
    // Use event delegation for dynamically added elements
    $(document).on('shown.bs.dropdown', '.label-dropdown', function() {
        console.log('Dropdown shown, availableClasses:', availableClasses);
        const $dropdown = $(this).find('.class-options-container');
        
        // Only populate if empty
        if ($dropdown.children().length === 0) {
            console.log('Populating dropdown...');
            if (availableClasses && availableClasses.length > 0) {
                // Create radio buttons for each class
                availableClasses.forEach(function(cls) {
                    // Create a unique ID for each radio button
                    const radioId = 'class_' + cls.replace(/\s+/g, '_').toLowerCase();
                    
                    $dropdown.append(`
                        <div class="form-check mb-2">
                            <input class="form-check-input class-radio" type="radio" name="classOptions" 
                                id="${radioId}" value="${cls}" data-class="${cls}">
                            <label class="form-check-label" for="${radioId}">
                                ${cls}
                            </label>
                        </div>
                    `);
                });
                
                console.log('Dropdown populated with', availableClasses.length, 'items');
            } else {
                console.error('No classes available to populate dropdown');
                $dropdown.append('<div class="text-muted">No classes available</div>');
            }
        }
    });
    
    // Handle class selection via radio buttons
    $(document).on('change', '.class-radio', function(e) {
        const selectedClass = $(this).data('class');
        const $predictionResult = $(this).closest('.prediction-result');
        const predictionId = $predictionResult.data('prediction-id');
        
        console.log('Class selected:', selectedClass, 'for prediction ID:', predictionId);
        
        // Send feedback to server
        $.ajax({
            type: 'POST',
            url: '/feedback',
            data: JSON.stringify({
                prediction_id: predictionId,
                corrected_class: selectedClass
            }),
            contentType: 'application/json',
            dataType: 'json',
            success: function(response) {
                console.log('Feedback response:', response);
                if (response.success) {
                    // Update the displayed class
                    $predictionResult.find('.prediction-label').text(selectedClass);
                    
                    // Close the dropdown
                    const dropdownEl = $predictionResult.find('.dropdown')[0];
                    const dropdown = bootstrap.Dropdown.getInstance(dropdownEl);
                    if (dropdown) {
                        dropdown.hide();
                    }
                    
                    // Show success toast
                    const toast = new bootstrap.Toast(document.getElementById('feedbackToast'));
                    toast.show();
                }
            },
            error: function(xhr, status, error) {
                console.error('Feedback error:', status, error);
                alert('Error submitting feedback. Please try again.');
            }
        });
    });
    
    // Make pencil icon more visible on hover
    $(document).on('mouseenter', '.label-dropdown', function() {
        $(this).find('.edit-btn').css('opacity', '1');
    }).on('mouseleave', '.label-dropdown', function() {
        $(this).find('.edit-btn').css('opacity', '0.6');
    });
});